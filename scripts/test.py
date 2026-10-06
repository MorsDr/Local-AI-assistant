from ddgs import DDGS
from urllib.parse import parse_qs, urlparse

query="Python programing"
result=DDGS().text(query, max_results=1)

def parse_url(url):
    if not url:
        print("No url geted!!")
        return {}
    parsed=urlparse(url)
    domain=parsed.netloc.lower()
    if ":" in domain:
        domain=domail.split(":")[0]
    domain_parts=domain.split(".")
    subdomain_qtty=None
    if len(p for p in domain_parts if p!="www") > 2:
        subdomain_qtty=len(p for p in domain_parts if p!="www")

    file_extension=None
    is_direct_file=False
    path=parsed.path.strip("/")
    path_segm=[seg for seg in path.split("/") if seg] if path else []
    if path_segm:
        last_segm=path_segm[-1]
        if "." in last_segm:
            ext=last_segm.split(".")[-1].lower()
            if ext in ["pdf", "doc", "docx", "xls", "xlcx", "zip", "csv", "json"]:
                file_extension=ext
                is_direct_file=True
    slug=""
    if path_segm and not is_direct_file:
        slug_raw=path_segm[-1]
        slug=re.sub(r"[-_]", " ", slug_raw)
    return {
        "https": parsed.scheme=="https",
        "domain":domain,
        "subdomain_qtty": subdomain_qtty,
        "is_direct_file": is_direct_file,
        "file_extension": file_extension,
        "slug":slug,
    }
item=result[0]
url=item.get("href", "")
print(parse_url(url))
