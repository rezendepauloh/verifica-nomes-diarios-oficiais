#!/usr/bin/env python3
"""
setup_pdfjs.py
Baixa e prepara o bundle oficial do Mozilla PDF.js v4.5.136 no diretório static/pdfjs/.
Aplica os patches de inicialização limpa (sem PDF padrão de teste) e o listener
de postMessage para carregar documentos Base64 do Streamlit.
"""

import io
import os
import sys
import urllib.request
import zipfile
from pathlib import Path

# Garante que a raiz do projeto esteja no sys.path para importar src.security
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.security import safe_extract_zip, MAX_ZIP_UNCOMPRESSED_BYTES

PDFJS_VERSION = "4.5.136"
PDFJS_URL = f"https://github.com/mozilla/pdf.js/releases/download/v{PDFJS_VERSION}/pdfjs-{PDFJS_VERSION}-dist.zip"
TARGET_DIR = os.environ.get("PDFJS_TARGET_DIR") or os.path.join(os.getcwd(), "static", "pdfjs")
MAX_DOWNLOAD_PDFJS_BYTES = 50 * 1024 * 1024  # 50 MB


def setup_pdfjs():
    viewer_html = os.path.join(TARGET_DIR, "web", "viewer.html")
    if os.path.exists(viewer_html):
        print(f"✅ PDF.js v{PDFJS_VERSION} já está instalado em {TARGET_DIR}.")
        return

    print(f"📦 Baixando Mozilla PDF.js v{PDFJS_VERSION} de {PDFJS_URL}...")
    os.makedirs(TARGET_DIR, exist_ok=True)

    req = urllib.request.Request(PDFJS_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        content = resp.read(MAX_DOWNLOAD_PDFJS_BYTES + 1)
        if len(content) > MAX_DOWNLOAD_PDFJS_BYTES:
            raise ValueError("Bundle PDF.js excedeu o limite máximo de download seguro (50 MB).")

    print(f"📦 Descompactando de forma segura ({len(content)} bytes) em {TARGET_DIR}...")
    safe_extract_zip(content, Path(TARGET_DIR), max_total_bytes=MAX_ZIP_UNCOMPRESSED_BYTES)

    # 1. Patch no viewer.mjs: Remove o arquivo default de teste (compressed.tracemonkey-pldi-09.pdf)
    mjs_path = os.path.join(TARGET_DIR, "web", "viewer.mjs")
    if os.path.exists(mjs_path):
        with open(mjs_path, "r", encoding="utf-8") as f:
            c = f.read()
        c = c.replace('value: "compressed.tracemonkey-pldi-09.pdf"', 'value: ""')
        with open(mjs_path, "w", encoding="utf-8") as f:
            f.write(c)
        print("🔧 Patch aplicado em viewer.mjs (defaultUrl limpo).")

    # 2. Patch no viewer.html: Injeta o listener universal para carregar PDFs em base64 do Streamlit
    if os.path.exists(viewer_html):
        with open(viewer_html, "r", encoding="utf-8") as f:
            h = f.read()

        listener_code = """
    <script>
      // Listener universal para carregar PDF enviado pela janela mãe (Streamlit)
      window.addEventListener('message', function(event) {
        if (!event.data) return;
        if (event.data.type === 'LOAD_PDF_BASE64' && event.data.data) {
          const base64Str = event.data.data;
          const raw = window.atob(base64Str);
          const rawLength = raw.length;
          const array = new Uint8Array(new ArrayBuffer(rawLength));
          for (let i = 0; i < rawLength; i++) {
            array[i] = raw.charCodeAt(i);
          }

          function doOpen() {
            if (window.PDFViewerApplication && window.PDFViewerApplication.initialized) {
              window.PDFViewerApplication.open({
                data: array,
                originalUrl: event.data.filename || 'documento.pdf'
              });
            } else {
              setTimeout(doOpen, 100);
            }
          }
          doOpen();
        }
      });

      // Notifica parent quando o viewer estiver pronto
      window.addEventListener('DOMContentLoaded', () => {
        window.parent.postMessage({ type: 'PDF_VIEWER_READY' }, '*');
      });
    </script>
"""
        h = h.replace("</body>", listener_code + "\n  </body>")
        with open(viewer_html, "w", encoding="utf-8") as f:
            f.write(h)
        print("🔧 Patch aplicado em viewer.html (listener postMessage ativo).")

    print(f"🎉 PDF.js configurado com sucesso em {TARGET_DIR}!")


if __name__ == "__main__":
    setup_pdfjs()

