import re
from pathlib import Path
from typing import Dict, Tuple

import pytz

from synctogit.evernote.models import Note, NoteGuid, NoteMetadata
from synctogit.filename_sanitizer import denormalize_filename


class WorkingCopyNoteParser:
    note_html_header_fields_marks = (
        b"<!--+++++++++++++-->",
        b"<!----------------->",
    )

    @classmethod
    def note_to_html(cls, note: Note, timezone: pytz.BaseTzInfo) -> bytes:
        header = []
        header += [b"<!doctype html>"]
        header += [b"<!-- PLEASE DO NOT EDIT THIS FILE -->"]
        header += [b"<!-- All changes you've done here will be stashed on next sync -->"]
        start_mark, end_mark = cls.note_html_header_fields_marks
        header += [start_mark]
        for k in ["guid", "updateSequenceNum", "title", "created", "updated"]:
            k_ = re.sub('([A-Z]+)', r'_\1', k).lower()
            v = getattr(note, k_)
            if k in ["created", "updated"]:
                v = str(v.astimezone(timezone))
            v = str(v)
            assert '\n' not in v

            header += [b"<!-- %s: %s -->" % (k.encode(), v.encode())]

        header += [end_mark]
        header += [b""]

        assert not note.html.startswith(b'<!doctype')
        body = b'\n'.join(header) + note.html
        return body

    @classmethod
    def get_stored_note_metadata(
        cls, notes_dir, note_path: Path
    ) -> Tuple[NoteGuid, NoteMetadata]:
        dir_parts = note_path.relative_to(notes_dir).parents[0].parts
        if not (1 <= len(dir_parts) <= 2):
            raise CorruptedNoteError(
                "Note's dir depth is expected to be within 1 to 2 levels",
                note_path
            )
        file = note_path.name

        header_vars = cls._parse_note_header(note_path)
        try:
            name = (
                tuple(denormalize_filename(d) for d in dir_parts)
                + (header_vars['title'],)
            )
            note_metadata = NoteMetadata(
                dir=dir_parts,
                name=name,
                update_sequence_num=int(header_vars['updateSequenceNum']),
                file=file,
            )
            return header_vars['guid'].lower(), note_metadata
        except (KeyError, ValueError) as e:
            raise CorruptedNoteError(
                "Unable to retrieve note metadata: %s" % repr(e),
                note_path
            )

    @classmethod
    def _parse_note_header(cls, note_path: Path) -> Dict[str, str]:
        start_mark, end_mark = cls.note_html_header_fields_marks
        # We will compare them with the readline() output, which
        # lines end with a newline.
        start_mark += b'\n'
        end_mark += b'\n'

        line = b'start'  # I'm waiting for PEP-572 eagerly
        result = {}
        with open(str(note_path), 'rb') as f:
            # Skip lines before the starting mark
            while line != start_mark and line != b'':
                line = f.readline()

            if line == b'':  # EOF
                raise CorruptedNoteError(
                    'Unable to find the starting mark of the note metadata '
                    'header for %s' % note_path,
                    note_path
                )

            # Read the actual vars
            line = f.readline()
            while line != end_mark and line != b'':
                g = re.search(b'^<!-- ([a-zA-Z]+): (.+) -->$', line)
                if g is None:
                    raise CorruptedNoteError(
                        'Expected a metadata variable in the header, but '
                        'it hasn\'t been found in the line "%s" of the note '
                        '%s' % (line.decode().strip(), note_path),
                        note_path
                    )
                key = g.group(1).decode()
                value = g.group(2).decode()
                result[key] = value
                line = f.readline()

            if line == b'':  # EOF
                raise CorruptedNoteError(
                    'Unable to find the end mark of the note metadata '
                    'header for %s' % note_path,
                    note_path
                )
        return result


class CorruptedNoteError(ValueError):
    def __init__(self, message, note_path: Path):
        super().__init__(message)
        self.note_path = note_path
