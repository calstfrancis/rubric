"""ObservanceWikiWindow — shows the Wikipedia article for a liturgical observance."""

from __future__ import annotations

import re

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib

try:
    gi.require_version("WebKit", "6.0")
    from gi.repository import WebKit as _WebKit
except Exception:
    try:
        gi.require_version("WebKit2", "4.1")
        from gi.repository import WebKit2 as _WebKit
    except Exception:
        try:
            gi.require_version("WebKit2", "4.0")
            from gi.repository import WebKit2 as _WebKit
        except Exception:
            _WebKit = None


class ObservanceWikiWindow(Adw.Window):
    """Shows the Wikipedia article for a liturgical observance."""

    _CSS = b"""
body { font-family: sans-serif; font-size: 15px; line-height: 1.7;
       max-width: 680px; margin: 2em auto; padding: 0 1.5em;
       color: #1a1a1a; background: #fff; }
h1 { font-size: 1.6em; margin-bottom: 0.2em; }
h2 { font-size: 1.2em; margin-top: 1.4em; border-bottom: 1px solid #e0e0e0; padding-bottom: 0.2em; }
h3 { font-size: 1.05em; }
p  { margin: 0.7em 0; }
a  { color: #1a6bb5; }
figure, .mw-editsection, .mw-indicators, .noprint,
.navbox, .infobox, .reflist, .references, sup.reference,
.mw-references-wrap { display: none !important; }
img { max-width: 100%; height: auto; border-radius: 4px; }
"""

    def __init__(self, name: str, **kw):
        super().__init__(title=name, default_width=740, default_height=680, **kw)
        self.set_modal(False)

        tv = Adw.ToolbarView()
        hdr = Adw.HeaderBar()
        hdr.set_title_widget(Adw.WindowTitle(title=name, subtitle="Wikipedia"))
        tv.add_top_bar(hdr)

        if _WebKit is not None:
            self._wv = _WebKit.WebView()
            self._wv.set_vexpand(True); self._wv.set_hexpand(True)
            # Inject CSS after page loads
            self._wv.connect("load-changed", self._on_load_changed)
            tv.set_content(self._wv)
            self._fetch_article(name)
        else:
            sp = Adw.StatusPage(title="WebKit not available",
                                description="Install python3-webkit2gtk to view Wikipedia articles.",
                                icon_name="web-browser-symbolic")
            open_btn = Gtk.Button(label="Open in browser")
            open_btn.add_css_class("suggested-action")
            import urllib.parse as _up
            clean_name = re.sub(r'\s+\([A-Za-z]{3,9}\s+\d{1,2}\)\s*$', '', name).strip()
            article = self._WIKI_TITLES.get(clean_name) or self._WIKI_TITLES.get(name)
            article_slug = article if article else _up.quote(clean_name.replace(" ", "_"))
            url = f"https://en.m.wikipedia.org/wiki/{article_slug}"
            open_btn.connect("clicked", lambda _: Gio.AppInfo.launch_default_for_uri(url, None))
            sp.set_child(open_btn)
            tv.set_content(sp)

        self.set_content(tv)

    # Mapping from observance display name to Wikipedia article title.
    # Names not listed here are cleaned and used directly.
    _WIKI_TITLES: dict[str, str] = {
        "Epiphany of the Lord": "Epiphany_(holiday)",
        "Presentation of Christ (Candlemas)": "Candlemas",
        "Transfiguration of the Lord (Aug 6)": "Transfiguration_of_Jesus",
        "Mary, Mother of Our Lord": "Mary,_mother_of_Jesus",
        "Birth of John the Baptist": "Nativity_of_John_the_Baptist",
        "Feast of Peter and Paul": "Feast_of_Saints_Peter_and_Paul",
        "St Michael and All Angels (Michaelmas)": "Michaelmas",
        "Holy Innocents": "Massacre_of_the_Innocents",
        "All Hallows' Eve": "Halloween",
        "St Francis of Assisi / Season of Creation ends": "Francis_of_Assisi",
        "Season of Creation begins": "Season_of_Creation",
        "Season of Creation": "Season_of_Creation",
        "Season of Creation ends": "Season_of_Creation",
        "World Day of Prayer for the Care of Creation": "World_Day_of_Prayer_for_the_Care_of_Creation",
        "Week of Prayer for Christian Unity begins": "Week_of_Prayer_for_Christian_Unity",
        "Week of Prayer for Christian Unity ends (St Paul)": "Week_of_Prayer_for_Christian_Unity",
        "Week of Prayer for Christian Unity": "Week_of_Prayer_for_Christian_Unity",
        "National Day for Truth and Reconciliation (Canada)": "National_Day_for_Truth_and_Reconciliation",
        "National Day of Awareness for Missing and Murdered Indigenous Women and Girls (Canada)": "National_Inquiry_into_Missing_and_Murdered_Indigenous_Women_and_Girls",
        "National Day of Remembrance (Montréal Massacre)": "École_Polytechnique_massacre",
        "International Day for the Elimination of Racial Discrimination": "International_Day_for_the_Elimination_of_Racial_Discrimination",
        "International Day for the Elimination of Violence Against Women": "International_Day_for_the_Elimination_of_Violence_against_Women",
        "International Day for the Eradication of Poverty": "International_Day_for_the_Eradication_of_Poverty",
        "International Day of Innocent Children Victims of Aggression": "International_Day_of_Innocent_Children_Victims_of_Aggression",
        "International Day of Persons with Disabilities": "International_Day_of_Persons_with_Disabilities",
        "International Day of Peace": "International_Day_of_Peace",
        "International Day of the World's Indigenous Peoples": "International_Day_of_the_World%27s_Indigenous_Peoples",
        "International Women's Day": "International_Women%27s_Day",
        "16 Days of Activism Against Gender-Based Violence": "16_Days_of_Activism_against_Gender-Based_Violence",
        "Transgender Day of Remembrance": "Transgender_Day_of_Remembrance",
        "Pride Month": "Pride_Month",
        "Indigenous Sunday (UCC)": "Indigenous_Sunday",
        "Earth Sunday": "Earth_Day",
        "Pride Sunday": "Pride_Sunday",
        "Creation Sunday": "Season_of_Creation",
        "Remembrance Sunday": "Remembrance_Sunday",
        "All Saints Sunday": "All_Saints%27_Day",
        "Canadian Thanksgiving": "Thanksgiving_(Canada)",
        "Martin Luther King Jr. Day": "Martin_Luther_King_Jr._Day",
        "World Day of Prayer": "World_Day_of_Prayer",
        "St Joseph": "Joseph,_father_of_Jesus",
        "Annunciation of the Lord": "Annunciation",
        "St Nicholas Day": "Saint_Nicholas_Day",
        "St Stephen / Boxing Day": "Boxing_Day",
        "St John the Apostle": "John_the_Apostle",
        "St Benedict of Nursia": "Benedict_of_Nursia",
        "St Luke": "Luke_the_Evangelist",
        "Saints Cyril and Methodius": "Saints_Cyril_and_Methodius",
        "St Vincent de Paul": "Vincent_de_Paul",
        "World Tourism Day / St Vincent de Paul": "Vincent_de_Paul",
        "New Year's Day": "New_Year%27s_Day",
        "Holy Name of Jesus": "Holy_Name_of_Jesus",
        "Reformation Day": "Reformation_Day",
        "Remembrance Day (Canada)": "Remembrance_Day",
        "World AIDS Day": "World_AIDS_Day",
        "World Food Day": "World_Food_Day",
        "World Environment Day": "World_Environment_Day",
        "World Refugee Day": "World_Refugee_Day",
        "World Animal Day": "World_Animal_Day",
        "Coming Out Day": "National_Coming_Out_Day",
        "Earth Day": "Earth_Day",
        "Christmas Day": "Christmas",
    }

    def _fetch_article(self, name: str):
        import threading, urllib.request, urllib.parse, urllib.error
        # Look up canonical article title, stripping proximity suffixes like " (Mon Jun 21)"
        clean = re.sub(r'\s+\([A-Za-z]{3,9}\s+\d{1,2}\)\s*$', '', name).strip()
        article = self._WIKI_TITLES.get(clean) or self._WIKI_TITLES.get(name)
        if article:
            encoded = article  # already URL-encoded in the dict where needed
        else:
            encoded = urllib.parse.quote(clean.replace(" ", "_"))
        url = f"https://en.wikipedia.org/api/rest_v1/page/html/{encoded}"

        def fetch():
            try:
                req = urllib.request.Request(url, headers={
                    "User-Agent": "Rubric/1.0 (liturgy planner; contact calstfrancis@gmail.com)",
                    "Accept": "text/html"
                })
                with urllib.request.urlopen(req, timeout=15) as r:
                    html = r.read().decode("utf-8")
                css_tag = f"<style>{self._CSS.decode()}</style>"
                # Inject CSS into <head>
                if "<head>" in html:
                    html = html.replace("<head>", f"<head>{css_tag}", 1)
                else:
                    html = css_tag + html
                GLib.idle_add(self._wv.load_html, html, f"https://en.wikipedia.org/wiki/{encoded}")
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    GLib.idle_add(self._wv.load_uri,
                                  f"https://en.m.wikipedia.org/wiki/Special:Search?search={urllib.parse.quote(clean)}")
                else:
                    GLib.idle_add(self._show_error, f"HTTP {e.code}")
            except Exception as ex:
                GLib.idle_add(self._show_error, str(ex))

        threading.Thread(target=fetch, daemon=True).start()

    def _on_load_changed(self, wv, event):
        if _WebKit and event == _WebKit.LoadEvent.FINISHED:
            # Hide mobile header/footer via JS
            js = ("var s=document.createElement('style');"
                  "s.textContent='.header-container,.mw-footer,.mw-mf-page-center>div:not(#content){display:none}';"
                  "document.head.appendChild(s);")
            try:
                wv.evaluate_javascript(js, -1, None, None, None, None, None)
            except Exception:
                try:
                    wv.run_javascript(js, None, None, None)
                except Exception:
                    pass

    def _show_error(self, msg: str):
        sp = Adw.StatusPage(title="Could not load article", description=msg,
                            icon_name="network-error-symbolic")
        tv = self.get_content()
        if tv:
            tv.set_content(sp)
