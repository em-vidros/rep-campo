# -*- coding: utf-8 -*-
"""
Converte um .md deste projeto em HTML A4 e depois em PDF (Chrome headless).

Uso:  python3 tools/gerar_pdf.py docs/DOC_TECNICO_TI.md ~/saida.pdf
"""
import html as H
import io
import os
import re
import subprocess
import sys

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

CSS = """
@page { size: A4; margin: 16mm 15mm; }
* { box-sizing: border-box; }
body { font-family:-apple-system,'Helvetica Neue',Arial,sans-serif; color:#16211d;
       font-size:10.2pt; line-height:1.5; margin:0; }
h1 { font-size:19pt; color:#0f3d2e; margin:0 0 2mm; border-bottom:2.5pt solid #0f3d2e; padding-bottom:2mm; }
h2 { font-size:12.5pt; color:#0f3d2e; margin:7mm 0 2mm; border-bottom:.6pt solid #cfd8d3;
     padding-bottom:1mm; page-break-after:avoid; }
h3 { font-size:10.8pt; color:#1b6b4f; margin:5mm 0 1.5mm; page-break-after:avoid; }
p { margin:0 0 2.6mm; }
ul,ol { margin:0 0 3mm; padding-left:6mm; }
li { margin-bottom:1.4mm; }
code { font-family:'SF Mono',Menlo,monospace; font-size:8.9pt; background:#eef2f0;
       padding:.4mm 1.2mm; border-radius:1.5mm; }
table { width:100%; border-collapse:collapse; margin:0 0 4mm; font-size:9.1pt; page-break-inside:avoid; }
th { background:#0f3d2e; color:#fff; text-align:left; padding:1.8mm 2.2mm; font-size:8.6pt;
     text-transform:uppercase; letter-spacing:.2pt; }
td { border-bottom:.5pt solid #dfe4e1; padding:1.8mm 2.2mm; vertical-align:top; }
tr:nth-child(even) td { background:#f7f9f8; }
blockquote { background:#eef4f1; border-left:2.5pt solid #1b6b4f; margin:0 0 3.5mm;
             padding:2.5mm 3mm; font-size:9.4pt; page-break-inside:avoid; }
hr { border:0; border-top:.5pt solid #dfe4e1; margin:5mm 0; }
strong { color:#0f3d2e; }
.rodape { margin-top:8mm; padding-top:2.5mm; border-top:.5pt solid #dfe4e1;
          font-size:8pt; color:#6b7770; text-align:center; }
"""


def inline(t):
    t = H.escape(t)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", t)
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", t)      # PDF nao leva link
    return t


def md_para_html(md):
    out, i, ls = [], 0, md.split("\n")
    while i < len(ls):
        s = ls[i].strip()
        if not s:
            i += 1
            continue
        if s.startswith(">"):
            bloco = []
            while i < len(ls) and ls[i].strip().startswith(">"):
                bloco.append(ls[i].strip().lstrip(">").strip())
                i += 1
            out.append("<blockquote>%s</blockquote>" % inline(" ".join(bloco)))
            continue
        if s.startswith("|"):
            tab = []
            while i < len(ls) and ls[i].strip().startswith("|"):
                tab.append(ls[i].strip())
                i += 1
            cel = lambda r: [c.strip() for c in r.strip("|").split("|")]
            cab = cel(tab[0])
            corpo = [cel(r) for r in tab[2:]] if len(tab) > 2 else []
            out.append("<table><thead><tr>%s</tr></thead><tbody>%s</tbody></table>" % (
                "".join("<th>%s</th>" % inline(c) for c in cab),
                "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % inline(c) for c in r)
                        for r in corpo)))
            continue
        if re.match(r"^#{1,4} ", s):
            n = len(s) - len(s.lstrip("#"))
            out.append("<h%d>%s</h%d>" % (n, inline(s[n:].strip()), n))
            i += 1
            continue
        if s.startswith("---"):
            out.append("<hr>")
            i += 1
            continue
        if re.match(r"^\d+\. ", s) or s.startswith("- "):
            ordenada = bool(re.match(r"^\d+\. ", s))
            itens = []
            while i < len(ls):
                t = ls[i].strip()
                if re.match(r"^\d+\. ", t) or t.startswith("- "):
                    itens.append(re.sub(r"^(\d+\.|-)\s*", "", t))
                    i += 1
                elif ls[i].startswith("   ") and t and itens:
                    itens[-1] += " " + t          # continuacao do item anterior
                    i += 1
                else:
                    break
            tag = "ol" if ordenada else "ul"
            out.append("<%s>%s</%s>" % (tag, "".join("<li>%s</li>" % inline(x) for x in itens), tag))
            continue
        par = []
        while i < len(ls) and ls[i].strip() and not re.match(r"^([#>|\-]|\d+\.)", ls[i].strip()):
            par.append(ls[i].strip())
            i += 1
        if par:
            out.append("<p>%s</p>" % inline(" ".join(par)))
        else:
            i += 1
    return "\n".join(out)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    origem, destino = sys.argv[1], os.path.expanduser(sys.argv[2])
    md = io.open(origem, encoding="utf-8").read()
    html_path = os.path.splitext(origem)[0] + ".html"
    doc = ("<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'>"
           "<title>%s</title><style>%s</style></head><body>%s"
           "<div class='rodape'>EM Vidros &middot; REP Campo &middot; 01/09/2026</div>"
           "</body></html>" % (os.path.basename(origem), CSS, md_para_html(md)))
    io.open(html_path, "w", encoding="utf-8").write(doc)
    subprocess.run([CHROME, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                    "--print-to-pdf=" + destino, "file://" + os.path.abspath(html_path)],
                   capture_output=True)
    if os.path.exists(destino):
        print("[OK] %s (%d KB)" % (destino, os.path.getsize(destino) // 1024))
    else:
        print("[--] PDF nao foi gerado")
        sys.exit(1)


if __name__ == "__main__":
    main()
