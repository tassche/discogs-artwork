import artwork
import logging


### Let's download to our working directory.
artwork.directory=None


### The album covers we're looking for.
albums = [
    ('Arcade Fire', 'Funeral', 2004),
    ('Tame Impala', 'Innerspeaker', 2010),
    ('Tame Impala', 'Innerspeaker', 2010),
    ('Fake artist', 'Fake album title', None)
]


def set_up_logging():
    """Set up a logger with debug messages."""
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(levelname)s:%(message)s"))
    logger = logging.getLogger('artwork')
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)


if __name__ == '__main__':
    set_up_logging()

    ### Download the artwork.
    for artist, album, year in albums:
        try:
            artwork.get_cache(artist, album, year=year, alt=artwork.get_random)
        except artwork.ArtworkError:
            pass
