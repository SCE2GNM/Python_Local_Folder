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

