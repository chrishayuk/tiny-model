def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)


def is_prime(n):
    if n < 2:
        return False
    for i in range(2, int(n ** 0.5) + 1):
        if n % i == 0:
            return False
    return True


numbers = [1, 2, 3, 4, 5]
squares = [x ** 2 for x in numbers]
total = sum(squares)
print(f"sum of squares: {total}")
