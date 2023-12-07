import json
import os
import plistlib
import re
import sys

import spotipy


SPOTIFY_SECRETS_FILE_NAME = 'spotify_secrets.json'

AUDIO_KINDS = {
    'AAC audio file',
    'MPEG audio file',
    'Purchased AAC audio file',
}

VIDEO_KINDS = {
    'MPEG-4 video file',
    'Protected MPEG-4 video file',
    'Purchased MPEG-4 video file',
    'QuickTime movie file',
}


def fatal(msg):
    print(f'ERROR: {msg}')
    sys.exit(1)


def warn(msg):
    print(f'WARNING: {msg}')


info = print


def debug(msg):
    print(f'DEBUG: {msg}')


# def debug(msg):
#     pass


def authenticate():
    this_dir = os.path.dirname(__file__)
    secrets_file_path = os.path.join(this_dir, SPOTIFY_SECRETS_FILE_NAME)
    with open(secrets_file_path) as fp:
        secrets = json.load(fp)

    secrets_keys = (
        'client_id',
        'client_secret',
        'redirect_uri',
    )
    for key in secrets_keys:
        value = secrets.get(key)
        assert value
        env_key = 'SPOTIPY_' + key.upper()
        os.environ[env_key] = value

    creds = spotipy.oauth2.SpotifyClientCredentials(
        # cache_handler=spotipy.cache_handler.CacheFileHandler(cache_path='.spotipy_auth_cache')
        cache_handler=spotipy.cache_handler.MemoryCacheHandler()
    )
    client = spotipy.Spotify(client_credentials_manager=creds)
    return client


def iter_itunes_tracks(library_path):
    with open(library_path, mode='rb') as fp:
        library = plistlib.load(fp, fmt=plistlib.FMT_XML)
    tracks = library.get('Tracks', {})
    debug(f'Loaded {len(tracks)} tracks from "{library_path}"')

    for track_id, track in sorted(tracks.items()):
        if track.get('Track Type') != 'File':
            debug(f'skipping track {track_id}, not a file')
            continue
        kind = track.get('Kind')
        if kind in VIDEO_KINDS:
            debug(f'skipping track {track_id}, is a video')
            continue
        assert kind in AUDIO_KINDS
        if track.get('Genre') == 'Podcast':
            debug(f'skipping track {track_id}, is a podcast')
            continue

        yield {
            'album': track.get('Album'),
            'album_artist': track.get('Album Artist'),
            'artist': track.get('Artist'),
            'rating': track.get('Album Rating'),
            'title': track.get('Name'),
        }


def strip_album_suffix(album):
    match = re.search(r'(?P<album>.*) \(?Dis[ck] \d+\)?', album)
    if match:
        return match['album'].rstrip()
    match = re.search(r'(?P<album>.*) \(?Volume \d+\)?', album)
    if match:
        return match['album'].rstrip()
    return album


def test_spotipy(client):
    birdy_uri = 'spotify:artist:2WX2uTcsvV5OnS0inACecP'
    results = client.artist_albums(birdy_uri, album_type='album')
    albums = results['items']
    while results['next']:
        results = client.next(results)
        albums.extend(results['items'])

    for album in albums:
        print(album['name'])


def test_find_albums():
    library_path = os.path.join(os.getenv("USERPROFILE"), "Music/iTunes/iTunes Music Library.xml")

    found_album_uris = []
    missing_albums = []

    client = authenticate()
    searched_queries = set()
    for ii, track in enumerate(iter_itunes_tracks(library_path)):
        album = track['album']
        simplified_album = strip_album_suffix(album)
        album_artist = track['album_artist']

        query = f'artist:{album_artist} album:{simplified_album}'
        if query in searched_queries:
            continue
        searched_queries.add(query)
        result = client.search(q=query, type='album')
        # with open('c:/t/json.json', 'w') as fp:
        #     json.dump(result, fp, indent=2)
        # debug(result)

        items = result.get('albums', {}).get('items')
        if items:
            album = items[0]
            album_uri = album['uri']
            album_name = album['name']
            album_artist_uris = [artist['uri'] for artist in album['artists']]
            album_artist_names = [artist['name'] for artist in album['artists']]
            info(f'Found album: {album_name=} ({album_artist_names=})')
            found_album_uris.append(album_uri)
        else:
            missing_albums.append({'album': album, 'album_artist': album_artist})
            warn(f'No album found named "{album}" for artist "{album_artist}"')

        if (len(found_album_uris) + len(missing_albums)) >= 300:
            break

    data = dict(found_album_uris=found_album_uris, missing_albums=missing_albums)
    with open('C:/t/json.json', 'w') as fp:
        json.dump(data, fp, indent=2)


if __name__ == '__main__':
    try:
        test_find_albums()
    except KeyboardInterrupt:
        pass
