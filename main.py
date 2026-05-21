import json
import os
import subprocess
import traceback
import urllib.error
import urllib.request
from typing import Any

import boto3
import cv2
from PIL import Image


Y7_PROJECT_DIR = "/usr/src/yolov7"
Y7_WEIGHTS_PATH = os.path.join(Y7_PROJECT_DIR, "best.pt")

# Use a deterministic output path so we do not have to guess exp/exp2/exp3.
YOLO_RUNS_DIR = "/tmp/yolov7-runs"
YOLO_RUN_NAME = "media-detection"
YOLO_OUTPUT_DIR = os.path.join(YOLO_RUNS_DIR, YOLO_RUN_NAME)
YOLO_LABELS_DIR = os.path.join(YOLO_OUTPUT_DIR, "labels")

LOCAL_INPUT_IMAGE = "/tmp/original.jpg"

DETECTED_IMAGE_VARIANT = "OBJECTS_IDENTIFIED"
DETECTION_LABELS_VARIANT = "OBJECT_DETECTION_LABELS"

s3 = boto3.client("s3")


class StepFunctionReporter:
    def __init__(self, task_token: str | None = None):
        self.task_token = task_token or os.environ.get("TASK_TOKEN")
        self.client = boto3.client("stepfunctions") if self.task_token else None

    def send_success(self, output: dict | None = None):
        if self.client and self.task_token:
            print("✅ Sending task success to Step Functions...")
            self.client.send_task_success(
                taskToken=self.task_token,
                output=json.dumps(output or {"status": "done"}),
            )

    def send_failure(self, error: str = "TaskFailed", cause: str | None = None):
        if self.client and self.task_token:
            print("❌ Sending task failure to Step Functions...")
            self.client.send_task_failure(
                taskToken=self.task_token,
                error=error,
                cause=cause or "Unknown failure",
            )


def normalize_api_url(url: str) -> str:
    return url.rstrip("/")


def api_headers() -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    # Optional, if you eventually protect the internal media API with a bearer token.
    token = os.environ.get("MEDIA_API_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    return headers


def http_get_json(url: str) -> dict[str, Any]:
    print(f"🌐 GET {url}")

    req = urllib.request.Request(
        url=url,
        method="GET",
        headers=api_headers(),
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GET failed: {url} status={e.code} body={body}") from e


def http_post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    print(f"🌐 POST {url}")
    print(f"📦 Payload: {json.dumps(payload)}")

    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        url=url,
        data=data,
        method="POST",
        headers=api_headers(),
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"POST failed: {url} status={e.code} body={body}") from e


def get_original_variant_metadata(*, media_api_url: str, media_id: str) -> dict[str, Any]:
    """
    Calls:
      GET /media/{media_id}/variants/original

    Expected response:
      {
        "media_id": "...",
        "usage_type": "user-uploaded",
        "created_at": "...",
        "variant": "original",
        "media": {
          "variant": "ORIGINAL",
          "media_type": "image/jpeg",
          "s3_bucket": "...",
          "s3_key": "media/.../original.jpg"
        }
      }
    """
    url = f"{media_api_url}/media/{media_id}/variants/original"
    response = http_get_json(url)

    media = response.get("media")
    if not media:
        raise ValueError("Media API response did not include media object")

    s3_bucket = media.get("s3_bucket")
    s3_key = media.get("s3_key")

    if not s3_bucket or not s3_key:
        raise ValueError("Original variant response missing s3_bucket or s3_key")

    return response


def download_s3_object(*, bucket: str, key: str, destination: str) -> None:
    print(f"⬇️ Downloading s3://{bucket}/{key} to {destination}")

    os.makedirs(os.path.dirname(destination), exist_ok=True)

    with open(destination, "wb") as f:
        s3.download_fileobj(bucket, key, f)


def upload_s3_object(
        *,
        bucket: str,
        key: str,
        source_path: str,
        content_type: str,
) -> None:
    if not os.path.exists(source_path):
        raise FileNotFoundError(f"Cannot upload missing file: {source_path}")

    print(f"⬆️ Uploading {source_path} to s3://{bucket}/{key}")

    s3.upload_file(
        Filename=source_path,
        Bucket=bucket,
        Key=key,
        ExtraArgs={
            "ContentType": content_type,
        },
    )


def assert_image_readable(local_image_path: str) -> None:
    print(f"🧪 Sanity check on image path: {repr(local_image_path)}")

    if not os.path.isfile(local_image_path):
        raise FileNotFoundError(f"File does not exist: {local_image_path}")

    img = cv2.imread(local_image_path)
    if img is not None:
        print("✅ OpenCV successfully loaded the image.")
        return

    print("⚠️ OpenCV failed to read the image. Trying Pillow...")

    try:
        Image.open(local_image_path).verify()
        print("✅ Pillow can open the image. Likely an OpenCV codec issue.")
    except Exception as e:
        raise ValueError(f"Both OpenCV and Pillow failed to read the image: {e}") from e

    raise ValueError("cv2.imread() returned None - OpenCV could not read the image.")


def run_detection(local_image_path: str) -> dict[str, str]:
    """
    Runs YOLOv7 detect.py and returns local output paths.

    Output image:
      /tmp/yolov7-runs/media-detection/original.jpg

    Output labels:
      /tmp/yolov7-runs/media-detection/labels/original.txt
    """
    assert_image_readable(local_image_path)

    base_name = os.path.basename(local_image_path)
    name_root, _ = os.path.splitext(base_name)

    os.makedirs(YOLO_RUNS_DIR, exist_ok=True)

    print(f"🚀 Running detect.py on {local_image_path}")

    result = subprocess.run(
        [
            "python3",
            "detect.py",
            "--weights",
            Y7_WEIGHTS_PATH,
            "--conf",
            "0.8",
            "--img-size",
            "640",
            "--save-txt",
            "--project",
            YOLO_RUNS_DIR,
            "--name",
            YOLO_RUN_NAME,
            "--exist-ok",
            "--source",
            local_image_path,
        ],
        cwd=Y7_PROJECT_DIR,
        capture_output=True,
        text=True,
    )

    print("📤 Output from detect.py:")
    print(result.stdout)

    if result.returncode != 0:
        print("❌ detect.py stderr:")
        print(result.stderr)
        raise subprocess.CalledProcessError(
            result.returncode,
            result.args,
            output=result.stdout,
            stderr=result.stderr,
        )

    detected_image_path = os.path.join(YOLO_OUTPUT_DIR, base_name)
    labels_path = os.path.join(YOLO_LABELS_DIR, f"{name_root}.txt")

    if not os.path.exists(detected_image_path):
        raise FileNotFoundError(f"YOLO output image not found: {detected_image_path}")

    # If YOLO finds no objects, the label file may not exist.
    # Create an empty one so downstream steps have a consistent artifact.
    if not os.path.exists(labels_path):
        print("ℹ️ No YOLO labels file found. Creating empty labels artifact.")
        os.makedirs(os.path.dirname(labels_path), exist_ok=True)
        with open(labels_path, "w", encoding="utf-8") as f:
            f.write("")

    return {
        "detected_image_path": detected_image_path,
        "labels_path": labels_path,
    }


def build_detected_image_key(media_id: str) -> str:
    return f"media/{media_id}/objects_identified.jpg"


def build_detection_labels_key(media_id: str) -> str:
    return f"media/{media_id}/object_detection_labels.txt"


def register_existing_variant(
        *,
        media_api_url: str,
        media_id: str,
        variant: str,
        s3_bucket: str,
        s3_key: str,
        media_type: str,
        usage_type: str,
        source: str,
        metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Calls a register-existing endpoint.

    Suggested endpoint:
      POST /media/{media_id}/variants/{variant}/register

    Suggested request body:
      {
        "usage_type": "user-uploaded",
        "s3_bucket": "...",
        "s3_key": "...",
        "media_type": "image/jpeg",
        "source": "object-detection-model",
        "metadata": {...}
      }
    """
    url = f"{media_api_url}/media/{media_id}/variants/{variant}/register"

    payload = {
        "usage_type": usage_type,
        "s3_bucket": s3_bucket,
        "s3_key": s3_key,
        "media_type": media_type,
        "source": source,
    }

    if metadata:
        payload["metadata"] = metadata

    return http_post_json(url, payload)


def process_media(*, media_id: str, media_api_url: str) -> dict[str, Any]:
    media_api_url = normalize_api_url(media_api_url)

    original_response = get_original_variant_metadata(
        media_api_url=media_api_url,
        media_id=media_id,
    )

    original_media = original_response["media"]
    usage_type = original_response.get("usage_type") or "user-uploaded"

    source_bucket = original_media["s3_bucket"]
    source_key = original_media["s3_key"]

    download_s3_object(
        bucket=source_bucket,
        key=source_key,
        destination=LOCAL_INPUT_IMAGE,
    )

    detection_outputs = run_detection(LOCAL_INPUT_IMAGE)

    detected_image_key = build_detected_image_key(media_id)
    labels_key = build_detection_labels_key(media_id)

    upload_s3_object(
        bucket=source_bucket,
        key=detected_image_key,
        source_path=detection_outputs["detected_image_path"],
        content_type="image/jpeg",
    )

    upload_s3_object(
        bucket=source_bucket,
        key=labels_key,
        source_path=detection_outputs["labels_path"],
        content_type="text/plain",
    )

    detected_image_registration = register_existing_variant(
        media_api_url=media_api_url,
        media_id=media_id,
        variant=DETECTED_IMAGE_VARIANT,
        s3_bucket=source_bucket,
        s3_key=detected_image_key,
        media_type="image/jpeg",
        usage_type=usage_type,
        source="object-detection-model",
        metadata={
            "model": "yolov7",
            "weights": os.path.basename(Y7_WEIGHTS_PATH),
            "source_variant": "ORIGINAL",
        },
    )

    labels_registration = register_existing_variant(
        media_api_url=media_api_url,
        media_id=media_id,
        variant=DETECTION_LABELS_VARIANT,
        s3_bucket=source_bucket,
        s3_key=labels_key,
        media_type="text/plain",
        usage_type=usage_type,
        source="object-detection-model",
        metadata={
            "model": "yolov7",
            "format": "yolo_txt",
            "source_variant": "ORIGINAL",
        },
    )

    return {
        "status": "done",
        "media_id": media_id,
        "source": {
            "variant": "ORIGINAL",
            "s3_bucket": source_bucket,
            "s3_key": source_key,
        },
        "outputs": {
            "objects_identified": {
                "variant": DETECTED_IMAGE_VARIANT,
                "s3_bucket": source_bucket,
                "s3_key": detected_image_key,
            },
            "object_detection_labels": {
                "variant": DETECTION_LABELS_VARIANT,
                "s3_bucket": source_bucket,
                "s3_key": labels_key,
            },
        },
        "registrations": {
            "objects_identified": detected_image_registration,
            "object_detection_labels": labels_registration,
        },
    }


def main():
    reporter = StepFunctionReporter()

    try:
        media_id = os.environ.get("MEDIA_ID")
        media_api_url = os.environ.get("MEDIA_API_URL")

        if not media_id:
            raise ValueError("Missing required environment variable: MEDIA_ID")

        if not media_api_url:
            raise ValueError("Missing required environment variable: MEDIA_API_URL")

        output = process_media(
            media_id=media_id,
            media_api_url=media_api_url,
        )

        reporter.send_success(output)

    except Exception as e:
        cause = "".join(traceback.format_exception(type(e), e, e.__traceback__))
        print(cause)

        reporter.send_failure(
            error=type(e).__name__,
            cause=cause,
        )

        raise


if __name__ == "__main__":
    main()


# import os
# import subprocess
# import boto3
# import json
# import traceback
# import time
#
# Y7_PROJECT_DIR = "/usr/src/yolov7"
# Y7_EXP_DIR = os.path.join(Y7_PROJECT_DIR, "exp")
# Y7_LABELS_DIR = os.path.join(Y7_EXP_DIR, "labels")
#
# class StepFunctionReporter:
#     def __init__(self, task_token=None):
#         self.task_token = task_token or os.environ.get("TASK_TOKEN")
#         self.client = boto3.client("stepfunctions") if self.task_token else None
#
#     def send_success(self, output: dict = None):
#         if self.client and self.task_token:
#             print("✅ Sending task success to Step Functions...")
#             self.client.send_task_success(
#                 taskToken=self.task_token,
#                 output=json.dumps(output or {"status": "done"})
#             )
#
#     def send_failure(self, error="TaskFailed", cause=None):
#         if self.client and self.task_token:
#             print("❌ Sending task failure to Step Functions...")
#             self.client.send_task_failure(
#                 taskToken=self.task_token,
#                 error=error,
#                 cause=cause or "Unknown failure"
#             )
#
#     def __enter__(self):
#         return self
#
#     def __exit__(self, exc_type, exc_value, tb):
#         if exc_type is None:
#             self.send_success()
#         else:
#             cause = ''.join(traceback.format_exception(exc_type, exc_value, tb))
#             self.send_failure(error=exc_type.__name__, cause=cause)
#             return False  # Re-raise exception
#
#
#
# def parse_s3_path(s3_path):
#     if not s3_path.startswith("s3://"):
#         raise ValueError("Invalid S3 path")
#     bucket, key = s3_path.replace("s3://", "").split("/", 1)
#     return bucket, key
#
# def download_from_s3(s3_path, dest_path):
#     bucket, key = parse_s3_path(s3_path)
#     s3 = boto3.client("s3")
#     print(f"⬇️ Downloading {s3_path} to {dest_path} ...")
#     with open(dest_path, 'wb') as f:
#         s3.download_fileobj(bucket, key, f)
#
#
# import cv2
# from PIL import Image
#
# def run_detection(local_image_path):
#     print(f"🧪 Sanity check on image path: {repr(local_image_path)}")
#
#     if not os.path.isfile(local_image_path):
#         raise FileNotFoundError(f"❌ File does not exist: {local_image_path}")
#
#     img = cv2.imread(local_image_path)
#     if img is None:
#         print("⚠️ OpenCV failed to read the image. Investigating...")
#
#         # Try with Pillow to see if it's an OpenCV codec issue
#         try:
#             Image.open(local_image_path).verify()
#             print("✅ PIL can open the image. Likely an OpenCV codec issue.")
#         except Exception as e:
#             raise ValueError(f"❌ Both OpenCV and PIL failed to read the image: {e}")
#
#         # Optional: print OpenCV build info
#         print("\n📋 OpenCV build information:")
#         print(cv2.getBuildInformation())
#
#         raise ValueError("cv2.imread() returned None - OpenCV could not read the image.")
#
#     print("✅ OpenCV successfully loaded the image.")
#
#     print(f"🚀 Running detect.py on {local_image_path} ...")
#     result = subprocess.run([
#         "python3", "detect.py",
#         "--weights", os.path.join(Y7_PROJECT_DIR, "best.pt"),
#         "--conf", "0.8",
#         "--img-size", "640",
#         "--save-txt",
#         "--project", Y7_PROJECT_DIR,
#         "--source", local_image_path
#     ], capture_output=True, text=True)
#
#     print("📤 Output from detect.py:")
#     print(result.stdout)
#
#     if result.returncode != 0:
#         print("❌ detect.py failed:", result.stderr)
#         raise subprocess.CalledProcessError(result.returncode, result.args)
#
#
# def upload_results_to_s3(input_s3_path):
#     s3 = boto3.client("s3")
#     bucket, key = parse_s3_path(input_s3_path)
#     s3_prefix = os.path.dirname(key)
#     base_name = os.path.basename(key)
#     name_root, _ = os.path.splitext(base_name)
#
#     image_file = os.path.join(Y7_EXP_DIR, base_name)
#     label_file = os.path.join(Y7_LABELS_DIR, f"{name_root}.txt")
#
#     s3_image_key = f"{s3_prefix}/processed/{base_name}"
#     s3_label_key = f"{s3_prefix}/processed/labels/{name_root}.txt"
#
#     if os.path.exists(image_file):
#         print(f"⬆️ Uploading {image_file} to s3://{bucket}/{s3_image_key}")
#         s3.upload_file(image_file, bucket, s3_image_key)
#     else:
#         print(f"⚠️ Missing image file: {image_file}")
#
#     if os.path.exists(label_file):
#         print(f"⬆️ Uploading {label_file} to s3://{bucket}/{s3_label_key}")
#         s3.upload_file(label_file, bucket, s3_label_key)
#     else:
#         print(f"⚠️ Missing label file: {label_file}")
#
# def main():
#     with StepFunctionReporter():
#         bucket = os.environ.get("DATA_BUCKET")
#         order_id = os.environ.get("ORDER_ID")
#         s3_prefix = os.environ.get("S3_PREFIX", "orders")  # default fallback
#
#         if not bucket or not order_id:
#             raise ValueError("Missing required environment variables: DATA_BUCKET and/or ORDER_ID")
#
#         image_key = f"{s3_prefix}/{order_id}/user_image.jpg"
#         s3_path = f"s3://{bucket}/{image_key}"
#         local_tmp_file = os.path.join("/tmp", os.path.basename(image_key))
#
#         download_from_s3(s3_path, local_tmp_file)
#         run_detection(local_tmp_file)
#         upload_results_to_s3(s3_path)
#
# if __name__ == "__main__":
#     main()
