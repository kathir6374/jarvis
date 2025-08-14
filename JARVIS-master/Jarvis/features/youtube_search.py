# youtube_search.py
import webbrowser
import urllib.parse
import urllib.request
import re

def play_on_youtube(query: str, open_in_new: bool = True) -> str:
    """
    Searches YouTube for `query` and opens the first result.
    Returns the url opened or empty string on failure.
    """
    if not query:
        return ""

    params = urllib.parse.urlencode({"search_query": query})
    url = "http://www.youtube.com/results?" + params
    try:
        res = urllib.request.urlopen(url)
        html = res.read().decode()
        # find video ids (look for /watch?v=)
        match = re.search(r"\/watch\?v=(.{11})", html)
        if match:
            vid = match.group(1)
            final = f"https://www.youtube.com/watch?v={vid}"
            if open_in_new:
                webbrowser.open_new(final)
            else:
                webbrowser.open(final)
            return final
    except Exception as e:
        print("YouTube play error:", e)
    return ""
