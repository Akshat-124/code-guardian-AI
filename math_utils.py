# Live webhook secure check verification
def calculate_factorial(n: int) -> int:
    """
    Safely calculates the factorial of a non-negative integer.
    """
    if n < 0:
        raise ValueError("Factorial is not defined for negative integers.")
    if n == 0 or n == 1:
        return 1
        
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result
