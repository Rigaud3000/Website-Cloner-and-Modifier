import os
import shutil
import zipfile
import requests
import gradio as gr
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

visited_urls = set()

def is_valid_url(url, base_domain):
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and base_domain in parsed.netloc

def clean_filename(url):
    path = urlparse(url).path.strip("/")
    if not path:
        return "index.html"
    return path.replace("/", "_") + ".html"

def download_file(url, folder):
    filename = os.path.basename(urlparse(url).path)
    if not filename:
        filename = "file"
    local_path = os.path.join(folder, filename)
    try:
        r = requests.get(url, stream=True, timeout=10)
        if r.status_code == 200:
            with open(local_path, 'wb') as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
            return filename
    except:
        pass
    return None

def clone_page(url, base_url, output_folder, enhance=False):
    if url in visited_urls:
        return
    visited_urls.add(url)

    try:
        res = requests.get(url, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        base_domain = urlparse(base_url).netloc

        for tag, attr in [('link', 'href'), ('script', 'src'), ('img', 'src')]:
            for node in soup.find_all(tag):
                asset = node.get(attr)
                if asset:
                    full_url = urljoin(url, asset)
                    filename = download_file(full_url, output_folder)
                    if filename:
                        node[attr] = filename

        # Optionally enhance HTML using Gemini
        html = str(soup)
        if enhance:
            html = enhance_with_gemini(html)

        filename = clean_filename(url)
        with open(os.path.join(output_folder, filename), 'w', encoding='utf-8') as f:
            f.write(html)

        for a in soup.find_all('a', href=True):
            next_url = urljoin(url, a['href'])
            if is_valid_url(next_url, base_domain):
                clone_page(next_url, base_url, output_folder, enhance)

    except Exception as e:
        print(f"Error cloning {url}: {e}")

def zip_folder(folder_path, output_path):
    shutil.make_archive(output_path, 'zip', folder_path)

def enhance_with_gemini(html_code):
    prompt = (
        "Clean and enhance this HTML code. Add SEO comments, improve formatting, "
        "and explain layout where useful as comments. Return only valid HTML:\n\n"
        + html_code
    )
    model = genai.GenerativeModel("gemini-pro")
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print("Gemini Error:", e)
        return html_code  # fallback to original

def clone_website(url, enhance=False):
    visited_urls.clear()
    folder = "multi_page_site"
    zip_file = "multi_page_clone"
    if os.path.exists(folder):
        shutil.rmtree(folder)
    os.makedirs(folder, exist_ok=True)

    clone_page(url, url, folder, enhance)
    zip_folder(folder, zip_file)

    return f"{zip_file}.zip"

demo = gr.Interface(
    fn=clone_website,
    inputs=[
        gr.Textbox(label="Enter a website URL (same-domain only)"),
        gr.Checkbox(label="✨ Enhance HTML with Gemini AI?")
    ],
    outputs=gr.File(label="Download your cloned site as a ZIP"),
    title="🌐 AI-Powered Website Cloner",
    description="Clone websites with optional GPT-enhanced HTML. Cleans code and adds smart comments."
)

if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=int(os.environ.get("PORT", 7860))
    )
