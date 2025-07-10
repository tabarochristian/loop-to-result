from jupyter_client import KernelManager
from queue import Empty
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class JupyterExecutor:
    """Enhanced Jupyter kernel executor with better resource management and error handling."""
    
    def __init__(self):
        self.km = KernelManager(kernel_name="python3")
        self.kc = None
        self._start_kernel()

    def _start_kernel(self):
        """Start the Jupyter kernel with proper initialization."""
        try:
            self.km.start_kernel()
            self.kc = self.km.client()
            self.kc.start_channels()
            self._wait_for_ready()
            logger.info("Jupyter kernel started successfully")
        except Exception as e:
            logger.error("Failed to start Jupyter kernel: %s", str(e))
            self._shutdown_kernel()
            raise RuntimeError(f"Failed to start Jupyter kernel: {str(e)}")

    def _wait_for_ready(self, timeout: int = 10):
        """Wait for kernel to become ready with timeout."""
        try:
            self.kc.wait_for_ready(timeout=timeout)
        except RuntimeError:
            error_msg = f"Kernel not ready within {timeout} seconds"
            logger.error(error_msg)
            raise RuntimeError(error_msg)

    def execute(self, code: str, timeout: int = 30) -> str:
        """
        Execute code in the kernel with enhanced output handling.
        
        Args:
            code: Python code to execute
            timeout: Maximum execution time in seconds
            
        Returns:
            Combined output from execution (stdout + stderr)
        """
        if not self.kc:
            raise RuntimeError("Kernel client not initialized")
        
        msg_id = self.kc.execute(code)
        output = []
        error = None
        start_time = time.time()

        while True:
            try:
                msg = self.kc.get_iopub_msg(timeout=1)
            except Empty:
                if time.time() - start_time > timeout:
                    error = f"Execution timeout after {timeout} seconds"
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

            if msg_type in ['execute_result', 'display_data']:
                data = msg['content']['data']
                output.append(data.get('text/plain', ''))

        if error:
            logger.error("Execution error: %s", error)
            return f"Execution Error:\n{error}"
        
        return "\n".join(output).strip()

    def shutdown(self):
        """Properly shutdown the kernel and clean up resources."""
        if hasattr(self, 'kc') and self.kc:
            try:
                self.kc.stop_channels()
            except Exception as e:
                logger.warning("Error stopping kernel channels: %s", str(e))
        
        if hasattr(self, 'km') and self.km:
            try:
                self.km.shutdown_kernel(now=True)
            except Exception as e:
                logger.warning("Error shutting down kernel: %s", str(e))
        
        logger.info("Jupyter kernel shutdown complete")

    def __del__(self):
        """Destructor to ensure kernel is properly shutdown."""
        self.shutdown()