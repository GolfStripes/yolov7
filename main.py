import os
import boto3
import subprocess

Y7_PROJECT_DIR = "/usr/src/yolov7"
Y7_EXP_DIR = os.path.join(Y7_PROJECT_DIR, "exp")
Y7_LABELS_DIR = os.path.join(Y7_EXP_DIR, "labels")

def parse_s3_path(s3_path):
    if not s3_path.startswith("s3://"):
        raise ValueError("Invalid S3 path")
    bucket, key = s3_path.replace("s3://", "").split("/", 1)
    return bucket, key

def download_from_s3(s3_path, dest_path):
    bucket, key = parse_s3_path(s3_path)
    s3 = boto3.client("s3")
    print(f"⬇️ Downloading {s3_path} to {dest_path} ...")
    with open(dest_path, 'wb') as f:
        s3.download_fileobj(bucket, key, f)

def run_detection(local_image_path):
    print(f"🚀 Running detect.py on {local_image_path} ...")
    result = subprocess.run([
        "python3", "detect.py",
        "--weights", os.path.join(Y7_PROJECT_DIR, "best.pt"),
        "--conf", "0.8",
        "--img-size", "640",
        "--save-txt",
        "--project", Y7_PROJECT_DIR,
        "--source", local_image_path
    ], capture_output=True, text=True)

    print("📤 Output from detect.py:")
    print(result.stdout)

    if result.returncode != 0:
        print("❌ detect.py failed:", result.stderr)
        raise subprocess.CalledProcessError(result.returncode, result.args)

def upload_results_to_s3(input_s3_path):
    s3 = boto3.client("s3")
    bucket, key = parse_s3_path(input_s3_path)
    s3_prefix = os.path.dirname(key)
    base_name = os.path.basename(key)
    name_root, _ = os.path.splitext(base_name)

    image_file = os.path.join(Y7_EXP_DIR, base_name)
    label_file = os.path.join(Y7_LABELS_DIR, f"{name_root}.txt")

    s3_image_key = f"{s3_prefix}/processed/{base_name}"
    s3_label_key = f"{s3_prefix}/processed/labels/{name_root}.txt"

    if os.path.exists(image_file):
        print(f"⬆️ Uploading {image_file} to s3://{bucket}/{s3_image_key}")
        s3.upload_file(image_file, bucket, s3_image_key)
    else:
        print(f"⚠️ Missing image file: {image_file}")

    if os.path.exists(label_file):
        print(f"⬆️ Uploading {label_file} to s3://{bucket}/{s3_label_key}")
        s3.upload_file(label_file, bucket, s3_label_key)
    else:
        print(f"⚠️ Missing label file: {label_file}")

def main():
    s3_path = os.environ.get("INPUT")
    if not s3_path:
        raise ValueError("Missing INPUT env var")

    local_tmp_file = os.path.join("/tmp", os.path.basename(s3_path))
    download_from_s3(s3_path, local_tmp_file)
    run_detection(local_tmp_file)
    upload_results_to_s3(s3_path)

if __name__ == "__main__":
    main()