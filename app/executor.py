from jupyter_client import KernelManager
from queue import Empty
import time

class JupyterExecutor:
    """
    Maintains a persistent Jupyter Python kernel and executes code snippets.
    """

    def __init__(self):
        self.km = KernelManager(kernel_name="python3")
        self.km.start_kernel()
        self.kc = self.km.client()
        self.kc.start_channels()

        # Wait for kernel to be ready
        self._wait_for_ready()

    def _wait_for_ready(self, timeout=10):
        """Wait for kernel to signal it's ready."""
        try:
            self.kc.wait_for_ready(timeout=timeout)
        except RuntimeError:
            # Kernel did not become ready in time
            raise RuntimeError("Jupyter kernel not ready within timeout.")

    def execute(self, code, timeout=30):
        """
        Execute code in kernel and return combined stdout+stderr or error message.
        """
        msg_id = self.kc.execute(code)
        output = []
        error = None
        start_time = time.time()

        while True:
            try:
                msg = self.kc.get_iopub_msg(timeout=1)
            except Empty:
                # Timeout waiting for message, check overall timeout
                if time.time() - start_time > timeout:
                    error = "Execution timeout"
                    break
                continue

            if msg['parent_header'].get('msg_id') != msg_id:
                # Ignore unrelated messages
                continue

            msg_type = msg['msg_type']

            if msg_type == 'status' and msg['content']['execution_state'] == 'idle':
                # Execution finished
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
            return f"Error:\n{error}"
        else:
            return "".join(output).strip()

    def shutdown(self):
        """
        Shutdown the kernel and clean up resources.
        """
        try:
            self.kc.stop_channels()
            self.km.shutdown_kernel(now=True)
        except Exception:
            pass
