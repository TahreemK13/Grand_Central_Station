# Grand_Central_Station — setup from Zed

## 1. File structure
```
Grand_Central_Station/
├── CNAME                 (contains: www.tahreemkarim.xyz)
├── .nojekyll             (empty file)
├── index.html
├── now.html
├── science.html
├── art.html
├── travel.html
├── free-resources.html
├── style.css
└── images/
    ├── octopus.png        (large-screen hero)
    ├── agave.png          (small-screen hero, <768px)
    ├── RTI_logo1.2.png
    ├── VulvVizConcat.png
    ├── glass.png
    └── now-1.png … now-7.png   (Now page photos, top 4 then bottom 3)
```
Rename your Desktop images to match, or edit the `src="/images/..."` paths.
Save the Now photos from the Google Site before you unpublish it.

## 2. Create the repo and push (Zed terminal: `ctrl+``)
```bash
cd ~/path/to/Grand_Central_Station
git init -b main
git add .
git commit -m "Rebuild site as GitHub Pages"
gh auth login                     # once, if not already
gh repo create Grand_Central_Station --public --source=. --push
```
No `gh`? Create an empty repo on github.com, then:
```bash
git remote add origin https://github.com/TahreemK13/Grand_Central_Station.git
git push -u origin main
```

## 3. Turn on Pages
GitHub → repo → Settings → Pages → Source: *Deploy from a branch* → `main` / `/ (root)` → Save.
Under Custom domain, enter `www.tahreemkarim.xyz` → Save.

## 4. DNS (at your registrar)
- `www` CNAME → `tahreemk13.github.io` (replaces `ghs.googlehosted.com`)
- Apex `tahreemkarim.xyz` A records → 185.199.108.153, 185.199.109.153, 185.199.110.153, 185.199.111.153
- Leave `garden` and `risingtigers` records untouched.

## 5. Decommission Google Sites
1. Google Sites → your site → Settings (gear) → Custom domains → remove `www.tahreemkarim.xyz`.
2. Publish ▾ → Unpublish.
3. After the GitHub site is live, delete the site from Drive (optional).

## 6. Finish
Once DNS resolves (minutes to ~24h), tick **Enforce HTTPS** in Settings → Pages.

## Later updates
```bash
git add . && git commit -m "update" && git push
```
Free resources: replace each `href="#"` with the PDF's Drive share link.
