from playwright.sync_api import sync_playwright

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("http://localhost:8000")

    # Create dummy files to upload
    import os
    os.makedirs("jules-scratch/verification/dummy_folder/subdir", exist_ok=True)
    file1_path = "jules-scratch/verification/dummy_folder/file1.txt"
    file2_path = "jules-scratch/verification/dummy_folder/subdir/file2.txt"
    with open(file1_path, "w") as f:
        f.write("This is file1.")
    with open(file2_path, "w") as f:
        f.write("This is file2.")

    # Set the input files on the hidden input element
    page.set_input_files("input[type=file]", [file1_path, file2_path])

    page.screenshot(path="jules-scratch/verification/upload_verification.png")

    browser.close()

with sync_playwright() as playwright:
    run(playwright)
