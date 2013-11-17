artwork.py
==========

This module provides an easy way to download artwork for a music album
using the [Discogs][1] API.

Please take into account that requests to the Discogs API are throttled
by the server to one per second per IP address. Because images are much
more resource-intensive to serve, image requests are [limited][2] to 
1000 per day per IP address. 

To minimize the chance we will send requests beyond this limit, this 
module saves every downloaded image in the directory specified in 
`artwork.directory` which defaults to `~/.covers`. If `artwork.directory` is 
set to None, the images are saved in the current working directory.

[1]: http://www.discogs.com/
[2]: http://www.discogs.com/developers/accessing.html#rate-limiting


Usage
-----

There are three functions to retrieve the path to a downloaded image:

1.  `get_random(artist, album, year=None)`

    Find all releases matching the parameters, randomly select one and 
    download an image if any are available.
    
2.  `get_largest(artist, album, year=None)`

    Find all releases matching the parameters, find the images in all 
    of them and download the largest image available.
    
3.  `get_cache(artist, album, year=None, alt=get_random)`

    Search for artwork in `artwork.directory` and download it using the 
    function specified by `alt` if it could not be found.

All functions above can raise one of the following exceptions that 
inherit from the base exception `ArtworkError`:

-   `DiskError`

    If an error occurs while performing actions on local storage.

-   `ImageNotFoundError`

    If no image could be found in one or more Discogs releases.

-   `ReleaseNotFoundError`

    If no Discogs release could be found for the given parameters.

-   `ResourceError`

    If an error occurs while opening a URL.


There's also the class `ArtworkWorker` (inherits from `threading.Thread`) 
to retrieve artwork in a separate thread.


Example
-------

`example.py` shows how you could use `artwork.py` in your own Python program.

Running it in a terminal gives output similar to:

    $ python3 example.py
    DEBUG:opening http://api.discogs.com/database/search?year=2004&release_title=Funeral&type=master&artist=Arcade+Fire took 0.366 seconds
    DEBUG:6 releases found for Funeral by Arcade Fire
    DEBUG:opening http://api.discogs.com/releases/2482966 took 0.382 seconds
    DEBUG:1 primary images found in release 2482966 and 0 secondary images
    DEBUG:opening http://api.discogs.com/image/R-2482966-1286497707.jpeg took 1.35 seconds
    DEBUG:artwork saved as Arcade Fire - 2004 - Funeral.jpeg
    DEBUG:retrieving image took 2.59 seconds
    DEBUG:opening http://api.discogs.com/database/search?year=2010&release_title=Innerspeaker&type=master&artist=Tame+Impala took 0.369 seconds
    DEBUG:4 releases found for Innerspeaker by Tame Impala
    DEBUG:opening http://api.discogs.com/releases/2785620 took 1.39 seconds
    DEBUG:1 primary images found in release 2785620 and 1 secondary images
    DEBUG:opening http://api.discogs.com/image/R-2785620-1300938076.jpeg took 0.396 seconds
    DEBUG:artwork saved as Tame Impala - 2010 - Innerspeaker.jpeg
    DEBUG:retrieving image took 2.97 seconds
    DEBUG:artwork for Innerspeaker by Tame Impala found on disk
    DEBUG:opening http://api.discogs.com/database/search?release_title=Fake+album+title&type=master&artist=Fake+artist took 0.378 seconds
    ERROR:no results for Fake album title by Fake artist

