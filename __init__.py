"""Generate Playlist"""
#
# Copyright (C) 2026 Bob Swift
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, see <https://www.gnu.org/licenses/>.

# This plugin is based on the Picard 2 plugin "Generate M3U playlist" by
# Francis Chin, Sambhav Kothari and Chris Hylen.  See original code at
# https://github.com/metabrainz/picard-plugins/blob/5a63f009/plugins/playlist/playlist.py

import os.path

from PyQt6 import QtWidgets

from picard.const import VARIOUS_ARTISTS_ID
from picard.plugin3.api import (
    Album,
    BaseAction,
    PluginApi,
    t_,
)
from picard.util import make_filename_from_title


USER_GUIDE_URL = 'https://picard-plugins-user-guides.readthedocs.io/en/latest/generate_playlist/user_guide.html'


class Playlist:
    def __init__(self, filename: str) -> None:
        self.filename = filename
        self.entries = []
        self.headers = []

    def add_header(self, header: str) -> None:
        """Add a header line.

        Args:
            header (str): Header line to add.
        """
        self.headers.append(header + "\n")

    def write(self) -> None:
        """Write the playlist file."""
        b_lines = []
        for header in self.headers:
            b_lines.append(header.encode('utf-8'))

        for entry in self.entries:
            for row in entry:
                b_lines.append(row.encode('utf-8'))

        with open(self.filename, 'wb') as f:
            f.writelines(b_lines)


class PlaylistEntry(list):
    def __init__(self, playlist: Playlist, index: int) -> None:
        list.__init__(self)
        self.playlist = playlist
        self.index = index

    def add(self, entry_row: str) -> None:
        self.append(entry_row + "\n")


class GeneratePlaylist(BaseAction):
    TITLE = t_('ui.action.generate_playlist.title', "Generate playlist")

    def callback(self, objs: list[Album]) -> None:
        if not objs:
            return

        first_album = None

        # Find common path of all files to set default playlist save location
        files = []
        for album in objs:
            for track in album.tracks:
                if track.files:
                    for f in track.files:
                        files.append(f.filename)
                    first_album = first_album or album

        if not files:
            QtWidgets.QMessageBox.warning(
                self.api.tagger.window,
                self.api.tr('ui.dialog.no_files.title', "No Files"),
                self.api.tr(
                    'ui.dialog.no_files.text',
                    "There are no audio files matched to any of the selected albums, so no playlist entries to write.",
                ),
                QtWidgets.QMessageBox.StandardButton.Ok,
                QtWidgets.QMessageBox.StandardButton.Ok,
            )

            return

        try:
            current_directory = os.path.commonpath(files)

        except ValueError:
            current_directory = ''

        if not current_directory:
            current_directory = self.api.global_config.setting['move_files_to'] or ''

        artist_id = first_album.metadata.get('musicbrainz_albumartistid', "")
        album_artist = first_album.metadata.get('albumartist', "Unknown Artist")
        album_title = first_album.metadata.get('album', "Unknown Album")

        default_filename = (
            make_filename_from_title(
                album_title if artist_id == VARIOUS_ARTISTS_ID else f"{album_artist} - {album_title}"
            )
            + ".m3u8"
        )

        filename, _selected_format = QtWidgets.QFileDialog.getSaveFileName(
            None,
            self.api.tr('ui.dialog.save_playlist.title', "Save new playlist"),
            os.path.join(current_directory, default_filename),
            self.api.tr('ui.dialog.save_playlist.filter', "Playlist") + "(*.m3u8 *.m3u)",
        )
        if not filename:
            return

        playlist = Playlist(filename)
        playlist.add_header("#EXTM3U")

        for album in objs:
            for track in album.tracks:
                if track.files:
                    entry = PlaylistEntry(playlist, len(playlist.entries))
                    playlist.entries.append(entry)

                    # M3U EXTINF row
                    track_length_seconds = int(round(track.metadata.length / 1000.0))
                    entry.add(
                        "#EXTINF:{duration:d},{artist} - {title}".format(
                            duration=track_length_seconds,
                            artist=track.metadata.get("artist", "Unknown"),
                            title=track.metadata.get("title", "Unknown"),
                        )
                    )

                    # M3U URL row - Extract the path from the first matched file object
                    first_file = track.files[0]
                    audio_filename = first_file.filename

                    try:
                        audio_filename = os.path.relpath(audio_filename, os.path.dirname(filename))
                    except ValueError:
                        pass

                    entry.add(str(audio_filename))

        try:
            playlist.write()

        except OSError as ex:
            self.api.logger.error(f"Error writing the playlist file: {filename}  ({ex})")
            QtWidgets.QMessageBox.critical(
                self.api.tagger.window,
                self.api.tr('ui.dialog.save_error.title', "Save Error"),
                self.api.tr('ui.dialog.save_error.text', "Error writing the playlist file.\n\nFile: %s\n\nError: %s")
                % (
                    filename,
                    ex,
                ),
                QtWidgets.QMessageBox.StandardButton.Ok,
                QtWidgets.QMessageBox.StandardButton.Ok,
            )


def enable(api: PluginApi):
    """Called when plugin is enabled."""
    api.register_album_action(GeneratePlaylist)
