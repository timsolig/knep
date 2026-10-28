# nowcast

Nederbördsprognos för de kommande två timmarna, byggd på SMHI:s öppna radarkomposit. Räknas på en Raspberry Pi var femte minut och visas på GitHub Pages.

```
SMHI radar (GeoTIFF, var 5:e min)
  → Pi: nowcast (pysteps: Lucas-Kanade och extrapolering, 24 steg à 5 min)
  → PNG-rutor och manifest.json
  → publish.sh: tvingar grenen data till en commit och startar workflowet pages
  → GitHub Actions: web/ från main plus data → GitHub Pages
```

## GitHub

1. Repot ska vara publikt.
2. Settings → Pages → Source: **GitHub Actions**.
3. Skapa en fine-grained token som bara gäller repot, med Contents och Actions satta till read and write.

## Raspberry Pi

pysteps saknar färdiga hjul för arm64 och kompileras vid installationen.

```sh
sudo apt install build-essential git
curl -LsSf https://astral.sh/uv/install.sh | sh
git clone https://github.com/<ägare>/nowcast ~/nowcast
cd ~/nowcast && uv sync

cat > ~/.config/nowcast.env <<EOF
GITHUB_REPO=<ägare>/nowcast
GITHUB_TOKEN=github_pat_...
EOF
chmod 600 ~/.config/nowcast.env
```

Prova en cykel för hand:

```sh
set -a; . ~/.config/nowcast.env; set +a
deploy/run.sh
```

Starta timern:

```sh
mkdir -p ~/.config/systemd/user
cp deploy/nowcast.service deploy/nowcast.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now nowcast.timer
loginctl enable-linger "$USER"   # timern går även utan inloggning
journalctl --user -u nowcast -f
```

## Utvecklingsmiljö med Claude Code

`dev/` innehåller en container med Claude Code, GitHub CLI och uv. Den monterar `~/nowcast-dev` som `/work` och `~/radar-arkiv` som `/data`. Driften ovan använder en separat klon i `~/nowcast`.

```sh
cd ~/nowcast-dev/dev && docker compose up -d --build
docker exec -it nowcast-dev bash
```

## Utveckla

```sh
uv run pytest                          # syntetiska data, inget nätverk
uv run nowcast --out web/data          # senaste radarbilden
uv run nowcast --time 2026-07-14T15:30 --out web/data   # historisk analys
python3 -m http.server -d web 8000     # sidan på localhost:8000
```

Radardata: SMHI, CC BY 4.0.
