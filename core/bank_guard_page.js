(function () {
  // Safeer BankGuard page signals. Runs locally in the page, sends nothing anywhere.
  // Only pages that show a password, one-time code, card, tax-number or PIN field are described further.
  var q = function (s) { try { return document.querySelector(s); } catch (e) { return null; } };
  var visible = function (el) {
    try {
      if (!el || el.type === "hidden" || el.disabled) return false;
      var r = el.getBoundingClientRect();
      if (r.width < 2 || r.height < 2) return false;
      var st = window.getComputedStyle(el);
      return st.visibility !== "hidden" && st.display !== "none" && parseFloat(st.opacity || "1") > 0.05;
    } catch (e) { return false; }
  };
  var shown = function (s) {
    try {
      var list = document.querySelectorAll(s);
      for (var i = 0; i < list.length && i < 50; i++) if (visible(list[i])) return list[i];
    } catch (e) {}
    return null;
  };
  var password = shown('input[type="password"]');
  var otp = shown('input[autocomplete="one-time-code"], input[name*="otp" i], input[id*="otp" i], input[name*="sms" i], input[name*="token" i][type="text"], input[inputmode="numeric"][maxlength="6"]');
  var card = shown('input[autocomplete^="cc-"], input[name*="cardnumber" i], input[name*="card_number" i], input[name*="kartic" i], input[name*="pan" i][inputmode="numeric"]');
  // Labels are the only reliable hint for tax-number and PIN fields; names differ from form to form.
  var labelled = function (re) {
    try {
      var labels = document.querySelectorAll("label, [aria-label], [placeholder]");
      for (var k = 0; k < labels.length && k < 200; k++) {
        var el = labels[k];
        var words = (el.tagName === "LABEL" ? el.innerText : "") + " " + (el.getAttribute("aria-label") || "") + " " + (el.getAttribute("placeholder") || "");
        if (!re.test(words)) continue;
        var target = el.tagName === "LABEL" ? (el.control || (el.htmlFor ? document.getElementById(el.htmlFor) : el.querySelector("input"))) : el;
        if (target && target.tagName === "INPUT" && visible(target)) return target;
      }
    } catch (e) {}
    return null;
  };
  // Slovenian tax number (davčna številka) and card PIN: real banks never ask for them on a login page.
  var taxid = shown('input[name*="davc" i], input[id*="davc" i], input[name*="taxid" i], input[name*="tax_id" i], input[name*="tax-id" i], input[name*="taxnumber" i], input[name*="vatid" i], input[name*="vat_id" i]') ||
    labelled(/dav[cč]n[ao]\s*[sš]t|tax\s*(id|number)|vat\s*(id|number)/i);
  var pin = shown('input[name="pin" i], input[id="pin" i], input[name*="pincode" i], input[name*="pin_code" i], input[name*="pin-code" i], input[name*="cardpin" i], input[name*="card_pin" i], input[autocomplete="cc-csc"][type="password"]') ||
    labelled(/(^|[^a-z])pin(?![a-z])/i);
  var result = { host: location.hostname, scheme: location.protocol.replace(":", ""),
                 password: !!password, otp: !!otp, card: !!card, taxid: !!taxid, pin: !!pin };
  if (!password && !otp && !card && !taxid && !pin) return result;
  var clip = function (value, max) { return String(value || "").replace(/\s+/g, " ").trim().slice(0, max); };
  var meta = function (sel) { var m = q(sel); return m ? (m.getAttribute("content") || "") : ""; };
  // News articles and blog posts about a bank are not login pages, even with a visible login box.
  result.article = /article|blogposting/i.test(meta('meta[property="og:type"]')) || !!q('[itemtype*="Article" i], [itemtype*="BlogPosting" i]') ||
    /"@type"\s*:\s*"(News)?Article|"@type"\s*:\s*"BlogPosting/.test((q('script[type="application/ld+json"]') || {}).textContent || "");
  result.title = clip(document.title, 200);
  result.site = clip(meta('meta[property="og:site_name"]') + " " + meta('meta[name="application-name"]'), 200);
  var headings = [];
  var hs = document.querySelectorAll("h1");
  for (var i = 0; i < hs.length && i < 2; i++) headings.push(clip(hs[i].innerText, 120));
  result.headings = headings.join(" | ");
  var logos = [];
  var imgs = document.querySelectorAll("header img, nav img, img[alt*='logo' i], img[src*='logo' i], img[class*='logo' i], img[id*='logo' i], [class*='logo' i] img, svg[aria-label], [class*='logo' i][aria-label]");
  for (var j = 0; j < imgs.length && logos.length < 8; j++) {
    var el = imgs[j];
    // Payment badges in footers and far down the page do not identify the site.
    try { if (el.closest("footer") || el.getBoundingClientRect().top + window.scrollY > 700) continue; } catch (e) {}
    var src = (el.getAttribute("src") || "").split("?")[0].split("/").pop();
    logos.push(clip((el.getAttribute("alt") || "") + " " + (el.getAttribute("aria-label") || "") + " " + src, 120));
  }
  var icon = q('link[rel~="icon"]');
  if (icon) logos.push(clip((icon.getAttribute("href") || "").split("?")[0].split("/").pop(), 80));
  result.logos = logos.join(" | ");
  result.text = clip(document.body ? document.body.innerText : "", 3000);
  return result;
})()
