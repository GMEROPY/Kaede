# Menjalankan
pip install -r requirements.txt
python app.py
Buka http://localhost:5000

- Untuk Instagram / konten yang butuh login: taruh cookies.txt (format Netscape) di folder ini.
- Untuk menggabungkan video+audio kualitas tinggi YouTube, pasang ffmpeg (opsional).

# Sumber tambahan: scrapr (opsional, Node.js)
Di Termux: pkg install nodejs && cd scrapr && npm install && cd ..
Tanpa Node, aplikasi tetap jalan dengan yt-dlp. Folder scrapr/ berisi salinan lib dari
github.com/coflyn/scrapr (lisensi MIT, lihat scrapr/LICENSE).

# YouTube MP4 (video + audio digabung)
Termux: pkg install ffmpeg
Kualitas maksimal default 720p. Ubah dengan: YT_MAX_HEIGHT=1080 python app.py
Pembaruan yt-dlp (YouTube sering berubah): pip install -U yt-dlp
