# artwork.py
# Copyright (C) 2013  Tijl Van Assche <tijlvanassche@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Module to retrieve artwork from Discogs.

This module provides an easy way to download artwork for a music album
using the Discogs API.

Please take into account that requests to the Discogs API are throttled
by the server to one per second per IP address. Because images are much
more resource-intensive to serve, image requests are limited to 1000 
per day per IP address. [1]

To minimize the chance we will send requests beyond this limit, this 
module saves every downloaded image in the directory specified in 
artwork.directory which defaults to ~/.covers. If artwork.directory is 
set to None, the images are saved in the current working directory.

There are three functions to retrieve the path to a downloaded image:

1.  get_random(artist, album, year=None)
    Find all releases matching the parameters, randomly select one and 
    download an image if any are available.
    
2.  get_largest(artist, album, year=None)
    Find all releases matching the parameters, find the images in all 
    of them and download the largest image available.
    
3.  get_cache(artist, album, year=None, alt=get_random)
    Search for artwork in artwork.directory and download it using the 
    function specified by alt if it could not be found.

All functions above can raise one of the following exceptions that 
inherit from the base exception ArtworkError:

-   DiskError
    If an error occurs while performing actions on local storage.

-   ImageNotFoundError
    If no image could be found in one or more Discogs releases.

-   ReleaseNotFoundError
    If no Discogs release could be found for the given parameters.

-   ResourceError
    If an error occurs while opening a URL.


    [1] http://www.discogs.com/developers/accessing.html#rate-limiting
"""
import logging
logger = logging.getLogger('artwork')

from collections import namedtuple
import json
import os
import random
import time
import urllib.request
import urllib.error
import urllib.parse

class ArtworkError(Exception):
    """Base class for artwork errors."""
    pass

class ImageNotFoundError(ArtworkError):
    """Raised when no image could be found in a Discogs release."""
    pass

class ReleaseNotFoundError(ArtworkError):
    """Raised when no Discogs release could be found."""
    pass

class ResourceError(ArtworkError):
    """Raised when an error occurs while opening a URL."""
    pass

class DiskError(ArtworkError):
    """Raised when an OSError occurs while writing an image to disk, or
    when artwork.directory (if set) does not exist and could not be 
    created.
    """
    pass

directory='~/.covers'
"""The directory where to load or save the images, default ~/.covers."""

_version = 0.1
_url = 'https://github.com/vetl/discogs-artwork'

_candidate_exts = ('jpeg', 'jpg', 'png')
_Image = namedtuple('_Image', ('url', 'height', 'width'))

_discogs_api_url = 'http://api.discogs.com/'
_discogs_api_search = 'database/search'
_discogs_api_headers = {
    'User-Agent': 'artwork.py/{ver} +{url}'.format(ver=_version, url=_url),
}


def get_largest(artist, album, year=None):
    """Download the largest image findable and return its path on disk.
    
    Search for Discogs releases matching the given parameters. Search 
    all releases for their images and download the largest image of 
    all images in all releases.
    
    If a release has a primary image, take that image to compare it 
    with the images of other releases. If a release only has secondary 
    images, take all those to compare with the images of other 
    releases.
    
    This is a very slow and expensive way to retrieve artwork, but will
    generally return a high quality image.
    
    Raises ReleaseNotFoundError if no Discogs releases could be found 
    for the given parameters. Raises ImageNotFoundError if no image 
    could be found in any of the releases. Raises ResourceError if an 
    error occurs while opening a URL, eg. when retrieving a list of 
    Discogs releases or downloading an image. Raises DiskError if an
    image could not be saved to disk.
    
    Arguments:
    artist -- the artist
    album -- the album by the artist
    
    Keyword arguments:
    year -- the release year of the album (default None)
    """
    time_begin = time.time()
    releases = _fetch_discogs_releases(artist, album, year=year)
    images = list()
    for release in releases:
        try:
            images.append(_fetch_discogs_image_resources(release))
        except ImageNotFoundError:
            pass
    largest_image, largest_size = None, 0
    for image in images:
        if image.width * image.heigth > largest_size:
            largest_image = image
    if not largest_image:
        message = ("no image found for '{album}' by '{artist}'"
                   "".format(artist=artist, album=album))
        logger.error(message)
        raise ImageNotFoundError(message)
    target = _create_target(largest_image.url, artist, album, year=year)
    target = _save_image_to_disk(largest_image.url, target)
    time_end = time.time()
    logger.debug("retrieving image took {:.3g} seconds"
                 "".format(time_end - time_begin))
    return target


def get_random(artist, album, year=None):
    """Download an image and return its path on disk.
    
    Search for Discogs releases matching the given parameters. Take a 
    random release from the list and search it for images. Download the
    primary image of the release if available. If no primary images are
    found, download a randomly selected secondary image of the release.
    
    This is the fastest and least expensive way to retrieve artwork, 
    but does not garantuee a high quality image.
    
    Raises ImageNotFoundError if no image could be found in the used 
    release. You might want to catch this error and try again to find 
    an image in another (randomly selected) release. 
    
    Raises ReleaseNotFoundError if no Discogs releases could be found 
    for the given parameters. Raises ResourceError if an error occurs 
    while opening a URL, eg. when retrieving a list of Discogs releases
    or downloading an image. Raises DiskError if an image could not be 
    saved to disk.
    
    Arguments:
    artist -- the artist
    album -- the album by the artist
    
    Keyword arguments:
    year -- the release year of the album (default None)
    """
    time_begin = time.time()
    releases = _fetch_discogs_releases(artist, album, year=year)
    images = _fetch_discogs_image_resources(random.choice(releases))
    source = random.choice(images).url
    target = _create_target(source, artist, album, year=year)
    target = _save_image_to_disk(source, target)
    time_end = time.time()
    logger.debug("retrieving image took {:.3g} seconds"
                 "".format(time_end - time_begin))
    return target


def get_cache(artist, album, year=None, alt=get_random):
    """Return the path to an image on disk.
    
    Return the path to an image in artwork.directory if one exists. If
    no image is found on disk, call an alternative function using the 
    same parameters to download an image from Discogs and return its 
    path.
    
    Raises ReleaseNotFoundError if no Discogs releases could be found 
    for the given parameters. Raises ImageNotFoundError if no image 
    could be found in the used release. Raises ResourceError if an 
    error occurs while opening a URL, eg. when retrieving a list of 
    Discogs releases or downloading an image. Raises DiskError if an 
    image could not be saved to disk.
    
    Arguments:
    artist -- the artist
    album -- the album by the artist
    
    Keyword arguments:
    year -- the release year of the album (default None)
    alt -- the alternative function (default artwork.get_random)
    """
    return (_file_in_cache(artist, album, year=year) or
            alt(artist, album, year=year))


def _create_filename(artist, album, year=None):
    """Return a string that can be used as filename (without extension)
    for an artwork image.
    
    Arguments:
    artist -- the artist
    album -- the album
    
    Keyword arguments:
    year -- the release year of the album (default None)
    """
    artist = artist.replace('/', '-')
    album = album.replace('/', '-')
    if year:
        return '{} - {} - {}'.format(artist, year, album)
    else:
        return '{} - {}'.format(artist, album)


def _create_target(source, artist, album, year=None):
    """Return a target path to save artwork.
    
    The target path is the concatenation of directory (if set) and a 
    filename with the same extension as the source URL. The filename 
    is created with _create_filename.
    
    Arguments:
    source -- the URL to an image
    artist -- the artist
    album -- the album
    
    Keyword arguments:
    year -- the release year of the album (default None)
    """
    global directory
    target = '{}.{}'.format(_create_filename(artist, album, year=year), 
                            source.split('.')[-1])
    if directory:
        target = os.path.join(directory, target)
    else:
        target = os.path.join(target)
    return target


def _file_candidates(artist, album, year=None):
    """Return a list of file paths that might point to a cached image.
    
    Each file path is a concatenation of directory (if set), 
    _create_filename and an extension in _candidate_exts. Use these to 
    check if a cached image exists.
    
    Arguments:
    artist -- the artist
    album -- the album
    
    Keyword arguments:
    year -- the release year of the album (default None)
    """
    global directory
    filename = _create_filename(artist, album, year=year)
    candidates = [os.path.join('{}.{}'.format(filename, ext)) 
                  for ext in _candidate_exts]
    if directory:
        directory = os.path.expanduser(directory)
        candidates = [os.path.join(directory, fn) for fn in candidates]
    return candidates


def _file_in_cache(artist, album, year=None):
    """Return the file path to a cached image if it exists, otherwise 
    return None.
    
    Arguments:
    artist -- the artist
    album -- the album
    
    Keyword arguments:
    year -- the release year of the album (default None)
    """
    candidates = _file_candidates(artist, album, year=year)
    for candidate in candidates:
        if os.path.isfile(candidate):
            logger.debug("artwork for {album} by {artist} found on disk"
                         "".format(artist=artist, album=album))
            return candidate
    return None


def _fetch_discogs_releases(artist, album, year=None, master=True):
    """Return a list of URLs to a Discogs release.
    
    Raises ReleaseNotFoundError if no releases are found.
    
    Arguments:
    artist -- the artist
    album -- the album
    
    Keyword arguments:
    year -- the release year of the album (default None)
    master -- search Discogs for type 'master' rather than type 
        'release' (default True)
    """
    args = {
        'type': 'master' if master else 'release',
        'artist': artist, 
        'release_title': album,
    }
    if year: args['year'] = year 
    url = (_discogs_api_url, _discogs_api_search, '?', 
           urllib.parse.urlencode(args))
    response = _openurl(''.join(url), _discogs_api_headers)
    result = json.loads(str(response.read(), 'utf-8'))
    response.close()
    releases = [x['resource_url'] for x in result['results']]
    if not releases:
        message = ("no results for {album} by {artist}"
                   "".format(artist=artist, album=album))
        logger.error(message)
        raise ReleaseNotFoundError(message)
    logger.debug("{n} releases found for {album} by {artist}"
                 .format(n=len(releases), artist=artist, album=album))
    return releases


def _fetch_discogs_image_resources(release):
    """Return a list of images found in release.
    
    Each image is represented as a namedtuple _Image. If images of 
    type 'primary' are found, return these. If no primary images are 
    found, return the images of type 'secondary'. 
    
    Raises ImageNotFoundError if no images are found.
    
    Arguments:
    release -- a URL to a Discogs release
    """
    response = _openurl(release, headers=_discogs_api_headers)
    release_ = json.loads(str(response.read(), 'utf-8'))
    response.close()
    resources, secondaries = list(), list()
    try:
        images = release_['images']
        for image in images:
            if image['type'] == 'primary':
                resources.append(
                    _Image(url=image['resource_url'], height=image['height'],
                           width=image['width'])
                )
            else:
                secondaries.append(
                    _Image(url=image['resource_url'], height=image['height'],
                           width=image['width'])
                )
        logger.debug(
            "{np} primary images found in release {release} and {ns} "
            "secondary images".format(np=len(resources), ns=len(secondaries),
                                      release=release.split('/')[-1])
        )
    except KeyError:
        pass
    if not resources and secondaries:
        resources = secondaries
    if not resources:
        message = ("no images found in release {release}"
                   "".format(release=release.split('/')[-1]))
        logger.error(message)
        raise ImageNotFoundError(message)
    return resources


def _save_image_to_disk(resource, target):
    """Save an image to disk.
    
    If the directory in path doesn't exist, try to create it. Raises  
    DiskError if the directory creation fails or the image could not be
    saved to disk.
    
    Arguments:
    resource -- the URL to the image
    target -- the target path (filename with extension)
    """
    global directory
    target = os.path.expanduser(target)
    dirname = os.path.dirname(target)
    if directory and not os.path.isdir(dirname):
        try:
            os.makedirs(dirname)
            logger.debug("created directory {}".format(dirname))
        except OSError as e:
            message = "cannot create directory: {}".format(e.strerror)
            logger.error(message)
            raise DiskError(message)
    image = _openurl(resource, headers=_discogs_api_headers)
    try:
        with open(target, 'wb') as f:
            f.write(image.read())
        logger.debug("artwork saved as {}".format(target))
    except OSError as e:
        message = "saving artwork failed: {}".format(e.strerror)
        logger.error(message)
        raise DiskError(message)
    return target


def _openurl(url, headers={}):
    """Open a URL (HTTP GET) and return its response.
    
    For HTTP URLs this function returns a http.client.HTTPResponse 
    object. For file URLs (eg. an image) this function returns the 
    bytes.
    
    Raises ResourceError on errors.
    
    Arguments:
    url -- the URL to open
    
    Keyword arguments:
    headers -- the headers for the HTTP request as a dict (default {})
    """
    try:
        time_begin = time.time()
        request = urllib.request.Request(url, headers=headers)
        response = urllib.request.urlopen(request)
        time_end = time.time()
        logger.debug("opening {} took {:.3g} seconds"
                     "".format(url, time_end - time_begin))
    except urllib.error.HTTPError as e:
        time_end = time.time()
        logger.debug("opening {} failed, took {:.3g} seconds"
                     "".format(url, time_end - time_begin))
        error = "HTTP {} {}".format(e.code, e.reason)
        logger.error(error)
        raise ResourceError(error)
    except urllib.error.URLError as e:
        time_end = time.time()
        logger.debug("opening {} failed, took {:.3g} seconds"
                     "".format(url, time_end - time_begin))
        logger.error(e.reason)
        raise ResourceError(e.reason)
    except OSError as e:
        time_end = time.time()
        logger.debug("opening {} failed, took {:.3g} seconds"
                     "".format(url, time_end - time_begin))
        logger.error(e.strerror)
        raise ResourceError(e.strerror)
    return response


from threading import Thread

class ArtworkWorker(Thread):
    """Worker to retrieve a Discogs image for a given artist and album.
    
    Notifies its listeners upon completion. 

    A listener should implement two callbacks: 
    -   artwork_found(filename)
    -   artwork_not_found()
    """
    
    def __init__(self, artist, album, year=None):
        super(ArtworkWorker, self).__init__()
        
        self.artist = artist
        self.album = album
        self.year = year
        
        self.name = 'Artwork'
        self.listeners = list()
        
        self.retrieve_function = get_random
        self.max_retries = 5
        self._try = 0
        
    def add_listener(self, listener):
        self.listeners.append(listener)
        
    def remove_listener(self, listener):
        self.listeners.remove(listener)
    
    def run(self):
        self._get_artwork()
    
    def _get_artwork(self):
        try:
            filename = get_cache(self.artist, self.album, year=self.year, 
                                 alt=self.retrieve_function)
        except ImageNotFoundError as e:
            if (self.retrieve_function == get_random and 
                self._try <= self.max_retries):
                self._try += 1
                self._get_artwork()
            else:
                self.notify_failure()
        except ArtworkError as e:
            self.notify_failure()
        else:
            self.notify_success(filename)
    
    def notify_failure(self):
        for listener in self.listeners:
            listener.artwork_not_found()
    
    def notify_success(self, filename):
        for listener in self.listeners:
            listener.artwork_found(filename)

