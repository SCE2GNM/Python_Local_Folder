# write a function that calculates the future value of an investment
def calculate_future_value(principal, annual_interest_rate, years):
    """
    Calculates the future value of an investment.

    Args:
        principal (float): The initial amount of money.
        annual_interest_rate (float): The annual interest rate (as a decimal).
        years (int): The number of years the money is invested.

    Returns:
        float: The future value of the investment.
    """
    future_value = principal * (1 + annual_interest_rate) ** years
    return future_value

def calculate_simple_future_value(principal, annual_interest_rate, years):
    """
    Calculates the future value of an investment using simple interest.

    Args:
        principal (float): The initial amount of money.
        annual_interest_rate (float): The annual interest rate (as a decimal).
        years (int): The number of years the money is invested.

    Returns:
        float: The future value of the investment.
    """
    future_value = principal * (1 + annual_interest_rate * years)
    return future_value

if __name__ == "__main__":
    # Example: $10,000 invested at 5% for 20 years
    p = 10000
    r = 0.05
    t = 20

    compound_fv = calculate_future_value(p, r, t)
    simple_fv = calculate_simple_future_value(p, r, t)

    print(f"Comparing growth on ${p:,.2f} over {t} years at {r:.0%} interest:")
    print(f"Simple Interest Result:   ${simple_fv:,.2f}")
    print(f"Compound Interest Result: ${compound_fv:,.2f}")
    print(f"Difference:               ${compound_fv - simple_fv:,.2f}")
    print(f"The interest rate is {r:.0%}")
