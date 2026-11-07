// Jembatan Node -> Python. Pemakaian: node scrapr_bridge.js "<url>"
// Mencetak JSON: {status, result:{title, thumbnail, items:[{kind,url}]}} atau {status:false,message}
const host = (u) => { try { return new URL(u).hostname.toLowerCase(); } catch { return ""; } };
const has = (h, ...d) => d.some((x) => h === x || h.endsWith("." + x));

// platform -> daftar scraper berurutan (fallback otomatis)
function chain(h) {
  const L = (p) => require("./scrapr/lib/" + p);
  if (has(h, "tiktok.com", "tt.site")) { const t = L("tiktok"); return [t.snaptik, t.ssstik, t.tiktokio, t.savetik, t.tikdownloader]; }
  if (has(h, "instagram.com")) { const i = L("instagram"); return [i.direct, i.snapsave, i.indown, i.snapinsta]; }
  if (has(h, "twitter.com", "x.com")) { const t = L("twitter"); return [t.direct, t.tweeload, t.tvd, t.savetwt]; }
  if (has(h, "facebook.com", "fb.watch", "fb.com")) { const f = L("facebook"); return [f.snapsave, f.fdown]; }
  if (has(h, "pinterest.com", "pin.it")) { const p = L("pinterest"); return [p.direct, p.pindown]; }
  if (has(h, "reddit.com", "redd.it")) return [L("reddit").rapidsave];
  if (has(h, "soundcloud.com")) return [L("soundcloud").klickaud];
  if (has(h, "threads.net", "threads.com")) return [L("threads").threadster];
  if (has(h, "bilibili.com", "bilibili.tv", "b23.tv")) return [L("bilibili").direct];
  if (has(h, "douyin.com")) return [L("douyin").direct];
  if (has(h, "xiaohongshu.com", "xhslink.com", "rednote.com")) return [L("rednote").direct];
  return [];
}

const isPhoto = (t) => /photo|image|jpe?g|png|webp/i.test(t || "");

(async () => {
  const url = process.argv[2];
  const out = (o) => { process.stdout.write(JSON.stringify(o)); process.exit(0); };
  let scrapers;
  try { scrapers = chain(host(url)).filter(Boolean); } catch (e) { return out({ status: false, message: "scrapr belum terpasang: " + e.message }); }
  if (!scrapers.length) return out({ status: false, message: "situs tidak didukung scrapr" });
  let last = "gagal";
  for (const fn of scrapers) {
    try {
      const r = await fn(url);
      if (!r || !r.status || !r.result) { last = (r && r.message) || last; continue; }
      const d = (r.result.downloads || []).filter((x) => x && x.url);
      if (!d.length) { last = "tidak ada tautan unduhan"; continue; }
      const photos = d.filter((x) => isPhoto(x.type));
      const items = photos.length
        ? photos.map((x) => ({ kind: "photo", url: x.url }))
        : [{ kind: "video", url: d[0].url }];   // beberapa kualitas -> ambil yang pertama
      return out({ status: true, result: { title: r.result.title, thumbnail: r.result.thumbnail, items } });
    } catch (e) { last = e.message; }
  }
  out({ status: false, message: last });
})();
