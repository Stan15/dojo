import io
import sys
from contextlib import redirect_stdout, redirect_stderr
from dojo.cli import main

class MockCompletedProcess:
    def __init__(self, returncode: int, stdout: str, stderr: str):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr

def run_cli(tmp_path, *args, check=True):
    cli_args = ["--db", str(tmp_path / "dojo.sqlite3")] + list(args)
    
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    
    returncode = 0
    try:
        with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
            try:
                ret = main(cli_args)
                if ret is not None:
                    returncode = ret
            except SystemExit as exc:
                if isinstance(exc.code, int):
                    returncode = exc.code
                elif exc.code is None:
                    returncode = 0
                else:
                    returncode = 1
                    stderr_buf.write(str(exc.code))
    except Exception as e:
        returncode = 1
        stderr_buf.write(str(e))
        
    stdout = stdout_buf.getvalue()
    stderr = stderr_buf.getvalue()
    
    if check and returncode != 0:
        raise AssertionError(f"command failed: {cli_args}\nstdout={stdout}\nstderr={stderr}")
        
    return MockCompletedProcess(returncode, stdout, stderr)
