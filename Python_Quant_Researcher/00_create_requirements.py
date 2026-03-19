import os

# Define the dependencies strictly with newlines
content = """yfinance
pandas
numpy
matplotlib"""

# Write to the file
file_path = "requirements.txt"
with open(file_path, "w") as f:
    f.write(content)

print(f"SUCCESS: {file_path} has been created with 4 distinct lines.")
print("You can now run: pip install -r requirements.txt")