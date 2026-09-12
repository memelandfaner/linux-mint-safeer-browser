# Safeer Linux 1.0.23

YouTube keeps playing:

- No more "Video paused. Continue watching?": YouTube arms this prompt for every playback and cancels it only on its own activity signal (the one a real click, key or touch produces); refreshing the last-activity timestamp, as before, was not enough for every account. While a video or YouTube Music plays, the browser now reports activity through that signal every 20 seconds (driven by the media clock, so it also works in a background tab), and the scheduled warning, dialog and pause are dropped before they can appear. The same signal keeps autoplay from pausing after several videos.
- Should the dialog still show up, it is recognised by what it is (a single "Yes" button, or its text in Safeer's languages) and confirmed, and the video resumes; dialogs that ask a real question (with a cancel button) are left alone.

Everything runs locally in the page; nothing is sent anywhere.

Slovensko: YouTube in YouTube Music se ne ustavljata več z »Video paused. Continue watching?« (»Predvajanje je zaustavljeno. Želite nadaljevati?«). YouTube to opozorilo pripravi ob vsakem predvajanju in ga prekliče le ob lastnem signalu aktivnosti, kot ga sproži pravi klik ali tipka; zgolj osveževanje časa zadnje aktivnosti pri vseh računih ni zadoščalo. Brskalnik med predvajanjem zdaj vsakih 20 sekund poroča aktivnost po tej poti (vezano na uro predvajanja, zato deluje tudi v zavihku v ozadju), zato do opozorila in premora sploh ne pride. Če bi se okno kljub temu pokazalo, ga brskalnik prepozna in potrdi, predvajanje pa se nadaljuje.
