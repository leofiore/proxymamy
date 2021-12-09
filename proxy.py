import os
import asyncio
from aiohttp import web, ClientSession
from bs4 import BeautifulSoup, Tag, NavigableString
import soupsieve as sv
import re
from threading import Thread

routes = web.RouteTableDef()

TARGET_URL = os.environ.get("TARGET_URL")
CACHEABLE_URLS = os.environ.get("CACHEABLE_URLS", "").split(" ")


@routes.get("/")
async def index(request):
    async with ClientSession() as session:
        res = await session.get(
            TARGET_URL,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:94.0) Gecko/20100101 Firefox/94.0"
            },
        )

        document = BeautifulSoup(await res.text(), features="lxml")
    mainbody = rebuildpage(document, id="primaryTopWrapper")

    return web.Response(text=str(mainbody), content_type="text/html")


@routes.get("/{year}/{month}/{day}/{slug}/{slugid}/")
async def article(request):
    year, month, day, slug, slugid = (
        request.match_info["year"],
        request.match_info["month"],
        request.match_info["day"],
        request.match_info["slug"],
        request.match_info["slugid"],
    )
    async with ClientSession() as session:
        res = await session.get(
            f"{TARGET_URL}/{year}/{month}/{day}/{slug}/{slugid}",
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:94.0) Gecko/20100101 Firefox/94.0",
                "Referer": TARGET_URL,
            },
        )

        document = BeautifulSoup(await res.text(), features="lxml")
    mainbody = rebuildpage(document, id="contenuto_articolo")
    return web.Response(text=str(mainbody), content_type="text/html")


@routes.get("/__CACHE__/{cssdoc:.*.css}")
async def cssdocuments(request):
    cssdoc = request.match_info["cssdoc"]
    async with ClientSession() as session:
        res = await session.get(
            cssdoc,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:94.0) Gecko/20100101 Firefox/94.0",
                "Referer": TARGET_URL,
            },
        )
        sheet = await res.text()
    for cacheable in CACHEABLE_URLS + [TARGET_URL]:
        sheet = sheet.replace(cacheable, f"/__CACHE__/{cacheable}")
    return web.Response(body=sheet, content_type="text/css")


@routes.get("/{wpsomething:wp-.*}/{asset:.*}")
async def wp_assets(request):
    asset = request.match_info["asset"]
    wp_path = request.match_info["wpsomething"]
    async with ClientSession() as session:
        res = await session.get(
            f"{TARGET_URL}/{wp_path}/{asset}",
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:94.0) Gecko/20100101 Firefox/94.0",
                "Referer": TARGET_URL,
            },
        )
        body = await res.read()
        content_type = res.content_type
    return web.Response(body=body, content_type=content_type)


@routes.get("/__CACHE__/{remote:.*}")
async def wp_assets(request):
    remote = request.match_info["remote"]
    async with ClientSession() as session:
        res = await session.get(
            remote,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:94.0) Gecko/20100101 Firefox/94.0",
                "Referer": TARGET_URL,
            },
        )
        body = await res.read()
        content_type = res.content_type
    return web.Response(body=body, content_type=content_type)


@routes.get("/robots.txt")
async def robots(request):
    return web.Response(text="User-agent:*\nDisallow: /")


def rebuildpage(document, **kwargs):
    newdoc = BeautifulSoup(
        "<html><head></head><body></body></html>",
        features="lxml",
    )

    mainbody = document.find(**kwargs)
    rewrite_urls(document.find("body"))
    reconciliate_tree(newdoc.html.body, mainbody, document.find("body"))

    removable = []

    def finder(selector):
        found = False
        for node in selector.select(newdoc.html.body):
            found = True
            removable.append(node)
        if not found:
            cosmetic_unuseful.append(selector)
            cosmeticfilters.remove(selector)

    finders = []
    for sel in cosmeticfilters:
        finders.append(Thread(target=finder, args=(sel,)))
        finders[-1].start()

    while len(finders) > 0:
        finders[0].join()
        finders.pop(0)

    for r in removable:
        r.decompose()
    head = document.html.head

    for link in head.find_all("link"):
        newdoc.html.head.append(link)
    for style in head.find_all("style"):
        newdoc.html.head.append(style)

    rewrite_urls(newdoc.html.head)

    return newdoc


def clone(node):
    if isinstance(node, NavigableString):
        return type(node)(node)
    new = Tag(None, node.builder, node.name, node.namespace, node.nsprefix)
    new.attrs = dict(node.attrs)
    for attr in ("can_be_empty_element", "hidden"):
        setattr(new, attr, getattr(node, attr))
    return new


def reconciliate_tree(new, target, original):
    if not isinstance(original, Tag):
        return
    if not isinstance(new, Tag):
        return
    for child in original.children:
        if child == target:
            new.append(child)
            return
        newchild = clone(child)
        new.append(newchild)
        reconciliate_tree(newchild, target, child)


def rewrite_urls(tree):

    for link in tree.find_all("a"):
        href = link.get("href")
        if href and href.startswith(TARGET_URL):
            link["href"] = href.replace(TARGET_URL, "")
            continue
        for cacheable in CACHEABLE_URLS:
            if href and href.startswith(cacheable):
                link["href"] = href.replace(cacheable, f"/__CACHE__/{cacheable}")
                break

    for img in tree.find_all("img"):
        src = img.get("src")
        if src.startswith(TARGET_URL):
            img["src"] = f"/__CACHE__/{src}"
        for cacheable in CACHEABLE_URLS:
            if src.startswith(cacheable):
                img["src"] = src.replace(cacheable, f"/__CACHE__/{cacheable}")
        srcset = img.get("srcset")

        if srcset is not None:
            for cacheable in CACHEABLE_URLS:
                img["srcset"] = srcset.replace(cacheable, f"/__CACHE__/{cacheable}")
            img["srcset"] = srcset.replace(TARGET_URL, "")

    for link in tree.find_all("link"):
        href = link.get("href")
        if href.startswith(TARGET_URL):
            link["href"] = f"/__CACHE__/{href}"
            continue
        for cacheable in CACHEABLE_URLS:
            if href.startswith(cacheable):
                link["href"] = href.replace(cacheable, f"/__CACHE__/{cacheable}")
                break


# filter_regex = re.compile(r"^(\*?##)(.+)")
filter_regex = re.compile(r"([^#]*)##(.+)")
style_regex = re.compile(r":(style|has-text|matches-path)\([^()]*\)")
cosmeticfilters = []
cosmetic_unuseful = []


async def loadfilters(f):
    async with ClientSession() as session:
        res = await session.get(
            f,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:94.0) Gecko/20100101 Firefox/94.0"
            },
        )
        for rule in (await res.text()).split("\n"):
            if filter_regex.match(rule) is None:
                continue
            host, ruledef = filter_regex.match(rule).groups()
            if style_regex.match(ruledef):
                continue
            if host not in ("*", ""):
                inhost = False
                for h in host.split(","):
                    if h in TARGET_URL:
                        inhost = True
                        break
                if not inhost:
                    continue
            cosmeticfilters.append(sv.compile(ruledef))


async def init():
    await asyncio.gather(
        *[
            loadfilters(f)
            for f in (
                # "https://combinatronics.io/uBlockOrigin/uAssets/master/filters/filters.txt",
                "https://easylist-downloads.adblockplus.org/easylistitaly.txt",
            )
        ]
    )
    cosmeticfilters.insert(0, sv.compile("script"))


loop = asyncio.get_event_loop()
loop.run_until_complete(init())

app = web.Application()
app.add_routes(routes)
web.run_app(app, port=int(os.environ.get("PORT", 8080)))
