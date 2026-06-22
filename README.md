# Windows-Media-Controller
A lightweight desktop widget for Windows that displays the currently playing media from supported applications using the Windows Global System Media Transport Controls API.
The widget features song's cover art, media information, playback controls, a blurred dynamic background, and a clean modern UI inspired by Windows 11.
Features

•	 Displays currently playing song/video title

•	 Shows artist information

•	 Shows song information

•	 Displays song artwork thumbnails

•	 Dynamic blurred background based on the songs cover art

•	 Always-on-top toggle

•	 Draggable floating widget

•	 Rounded Windows 11 style design

•	 Lightweight and responsive

Python
•	Python 3.10 or newer (works best with Python 3.12)

Packages

pip install winsdk Pillow

How it works:
This project uses Microsoft's Global System Media Transport Controls (GSMTC) through the Windows SDK Python bindings.
The widget queries active media sessions and retrieves

•	Track title

•	Artist

•	Song's cover art

•	Playback status

•	Media controls

It then renders a custom Tkinter interface with Pillow-generated graphics and artwork effects.

Limitations

•	Windows only

•	Requires applications to expose media sessions through GSMTC

•	Some browser tabs may not provide album artwork

•	Many DRM-protected applications restrict metadata access
