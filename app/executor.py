from jupyter_client import KernelManager
from queue import Empty
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class JupyterExecutor:
    """
    Manages a persistent Jupyter Python kernel for code execution.
    """
    def __init__(self):
        self.km = KernelManager(kernel_name="python3")
        self.km.start_kernel()
        self.kc = self.km.client()
        self.kc.start_channels()
        self._wait_for_ready()

    def _wait_for_ready(self, timeout: int = 10):
        """
        Waits for the kernel to be ready.
        """
        try:
            self.kc.wait_for_ready(timeout=timeout)
            logger.info("Jupyter kernel ready")
        except RuntimeError:
            logger.error("Jupyter kernel not ready within timeout")
            raise RuntimeError("Jupyter kernel not ready within timeout")

    def execute(self, code: str, timeout: int = 30) -> str:
        """
        Executes code in the kernel and returns combined output or error.
        """
        msg_id = self.kc.execute(code)
        output = []
        error = None
        start_time = time.time()

        while True:
            try:
                msg = self.kc.get_iopub_msg(timeout=1)
            except Empty:
                if time.time() - start_time > timeout:
                    error = "Execution timeout"
                    break
                continue

            if msg['parent_header'].get('msg_id') != msg_id:
                continue

            msg_type = msg['msg_type']
            if msg_type == 'status' and msg['content']['execution_state'] == 'idle':
                break

            if msg_type == 'stream':
                output.append(msg['content']['text'])

            if msg_type == 'error':
                error = "\n".join(msg['content']['traceback'])
                break

            if msg_type == 'execute_result' or msg_type == 'display_data':
                data = msg['content']['data']
                if 'text/plain' in data:
                    output.append(data['text/plain'])

        if error:
            logger.error(f"Execution error: {error}")
            return f"Error:\n{error}"
        return "".join(output).strip()

    def shutdown(self):
        """
        Shuts down the kernel and cleans up resources.
        """
        try:
            self.kc.stop_channels()
            self.km.shutdown_kernel(now=True)
            logger.info("Jupyter kernel shutdown")
        except Exception as e:
            logger.error(f"Error shutting down kernel: {str(e)}")