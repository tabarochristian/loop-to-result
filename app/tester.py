import re

def extract_code_and_clean_text(text):
    """
    Extracts the first Python code block from markdown-style content.
    Returns a tuple:
    (code inside the block, text without the code block including delimiters)
    """
    # Regex to find the code block including delimiters
    match = re.search(r"```python\n(.*?)\n```", text, re.DOTALL)
    if match:
        code_only = match.group(1)             # Extract inner code
        full_block = match.group(0)            # Entire block with backticks
        cleaned_text = text.replace(full_block, "").strip()  # Remove block completely
        return code_only, cleaned_text
    return None, text.strip()




# Example usage
mixed_cell = """
I can see that there have been multiple attempts to write explanatory text directly in code cells, which is causing syntax errors in Jupyter Notebook. In Jupyter, code cells are meant for executable Python code, while text explanations should be written in Markdown cells.

Let me provide the correct Python code to generate Fibonacci numbers in a proper code cell format, along with explanations as comments within the code.

```python
# Function to generate Fibonacci numbers up to a specified count
def fibonacci(n):
    # Initialize the list with the first two Fibonacci numbers
    fib_sequence = [0, 1]
    
    # Generate subsequent numbers if count is greater than 2
    if n <= 0:
        return []
    elif n == 1:
        return [0]
    
    for i in range(2, n):
        # Next number is the sum of the previous two numbers
        fib_sequence.append(fib_sequence[i-1] + fib_sequence[i-2])
    
    return fib_sequence

# Test the function with a count of 10
count = 10
result = fibonacci(count)
print(f"Fibonacci sequence with {count} numbers: {result}")
```

This code defines a function `fibonacci(n)` that generates a list of the first `n` Fibonacci numbers. It starts with [0, 1] and iteratively adds the sum of the last two numbers to build the sequence. The output will show the Fibonacci sequence for the specified count (10 in this example).

If you want to add more detailed explanations or formatted text, I recommend creating a Markdown cell in Jupyter Notebook for that purpose. Let me know if you'd like me to explain any part of the code further or modify the example!
"""

code, text = extract_code_and_clean_text(mixed_cell)
print(text)