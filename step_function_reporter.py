import traceback
import json

class StepFunctionReporter:
    def __init__(self, task_token=None):
        self.task_token = task_token or os.environ.get("TASK_TOKEN")
        self.client = boto3.client("stepfunctions") if self.task_token else None

    def send_success(self, output: dict = None):
        if self.client and self.task_token:
            print("✅ Sending task success to Step Functions...")
            self.client.send_task_success(
                taskToken=self.task_token,
                output=json.dumps(output or {"status": "done"})
            )

    def send_failure(self, error="TaskFailed", cause=None):
        if self.client and self.task_token:
            print("❌ Sending task failure to Step Functions...")
            self.client.send_task_failure(
                taskToken=self.task_token,
                error=error,
                cause=cause or "Unknown failure"
            )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, tb):
        if exc_type is None:
            self.send_success()
        else:
            cause = ''.join(traceback.format_exception(exc_type, exc_value, tb))
            self.send_failure(error=exc_type.__name__, cause=cause)
            return False  # Re-raise exception
