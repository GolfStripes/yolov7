import os
import boto3
import subprocess

def main():
    s3_path = os.environ.get("INPUT")
    if not s3_path:
        raise ValueError("Missing INPUT env var")

    bucket, key = s3_path.replace("s3://", "").split("/", 1)
    s3 = boto3.client("s3")

    # Local filename to save image
    local_filename = os.path.join("/tmp", os.path.basename(key))

    # Download from S3 and write to disk
    print(f"⬇️ Downloading {s3_path} to {local_filename} ...")
    with open(local_filename, 'wb') as f:
        s3.download_fileobj(bucket, key, f)

    # Call detect.py and pass the file path
    print(f"🚀 Running detect.py on {local_filename} ...")
    result = subprocess.run(["python", "detect.py", local_filename], capture_output=True, text=True)

    print("📤 Output from detect.py:")
    print(result.stdout)

    if result.returncode != 0:
        print("❌ detect.py failed:", result.stderr)
        raise subprocess.CalledProcessError(result.returncode, result.args)

if __name__ == "__main__":
    main()

