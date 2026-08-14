import os
import zipfile
import urllib.request
import time


papers = {
    "2026": "https://www.cbse.gov.in/cbsenew/question-paper/2026/XII/Mathematics.zip",
    "2025": "https://www.cbse.gov.in/cbsenew/question-paper/2025/XII/MATHEMATICS.zip",
    "2024": "https://www.cbse.gov.in/cbsenew/question-paper/2024/XII/MATHEMATICS.zip",
    "2023": "https://www.cbse.gov.in/cbsenew/question-paper/2023/XII/MATHEMATICS.zip",
    "2022": "https://www.cbse.gov.in/cbsenew/question-paper/2022/XII/Math.zip"
}

# switch your dir accordingly 
output_root = r"C:\Users\niel\sandbox\mathpyqs"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def download_and_extract():
    if not os.path.exists(output_root):
        os.makedirs(output_root)
        print(f"created root directory: {output_root}")

    for year, url in papers.items():
        print(f"\n--- {year} ---")
        
        
        year_dir = os.path.join(output_root, year)
        zip_path = os.path.join(output_root, f"Mathematics_{year}.zip")
        
        if not os.path.exists(year_dir):
            os.makedirs(year_dir)
            
        print(f"downloading from: {url}")
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req) as response, open(zip_path, 'wb') as out_file:
                out_file.write(response.read())
            print(f"saved zip file to: {zip_path}")
            
            print(f"extracting to: {year_dir}")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(year_dir)
            print(f"extraction successful.")
            
            
            os.remove(zip_path)
            print("removed temporary zip file.")
            
        except Exception as e:
            print(f"error processing {year}: {e}")
            
        # Be polite to the server
        time.sleep(1.5)

    print("\ndownloads + extraction done.")

if __name__ == "__main__":
    download_and_extract()
