import logging
from datetime import timedelta, datetime
from math import fabs
from flexget.plugin import register_plugin, priority
from flexget.utils.log import log_once

log = logging.getLogger('my_movie_filter')


class MyMovieFilter(object):
    """
       Filters entries based on some crazy custom rules
    """
    
    required_fields = [
            'imdb_url', 'imdb_languages', 'imdb_votes', 'imdb_votes', 'rt_id', 'rt_releases',
            'rt_genres', 'rt_critics_rating', 'rt_audience_rating', 'rt_critics_score',
            'rt_audience_score', 'rt_average_score'
            ]
    languages = ['english']
    max_accept_ages = [(2,'new'), (10, 'recent'), (15, 'old'), (30, 'older'), (40, 'classic')]
    min_imdb_votes = 10000


    global_min_score = 70

    imdb_genres_reject = \
        ['musical']
    imdb_single_genres_strict = \
        {'drama': 95, 'romance': 97, 'animation': 90}
    imdb_genres_strict = \
        {'drama': 85, 'romance': 85, 'documentary': 83, 'horror': 86, 'animation': 86, 'family': 90}
    imdb_genres_accept_except = \
        ['animation', 'family', 'horror', 'romance', 'biography']
    imdb_genres_accept = \
        {'action': 52, 'sci-fi': 62, 'war': 62, 'crime': 62, 'comedy': 65, 'history': 70, 'mystery': 72, 'thriller': 72}

    rt_genres_ignore = \
        ['Classics', 'Cult Movies']
    rt_genres_reject = \
        ['Musical & Performing Arts', 'Anime & Manga', 'Faith & Spirituality', 'Gay & Lesbian']
    rt_single_genres_strict = \
        {'Drama': 90, 'Romance': 97, 'Art House & International Movies': 99}
    rt_genres_strict = \
        {'Drama': 85, 'Romance': 85, 'Documentary': 83, 'Horror': 86, 'Animation': 86,
            'Special Interest': 89, 'Kids & Family': 90, 'Art House & International Movies': 80}
    rt_genres_accept_except = \
        ['Animation', 'Kids & Family', 'Horror', 'Romance', 'Art House & International Movies']
    rt_genres_accept = \
        {'Action & Adventure': 52, 'Science Fiction & Fantasy': 62, 'Comedy': 65, 'Mystery & Suspense': 72}

    def validator(self):
        from flexget import validator
        return validator.factory('boolean')


    def check_fields(self, feed, entry):
        for field in self.required_fields:
            if not entry.get(field) and entry.get(field) != 0:
                feed.reject(entry, 'Required field %s is not present' % field)
                return False
        return True


    @priority(0) # Make filter run after other filters, but before exists_movies
    def on_feed_filter(self, feed, config):
        log.debug('Running custom filter')
        for entry in feed.entries:
            force_accept = False
            reasons = []
            
            if not self.check_fields(feed, entry):
                continue

            # Don't allow straight to DVD flicks
            if not entry['rt_releases'].get('theater', False):
                feed.reject(entry, 'No theater release date')
                continue

            # Enforce languages
            if entry['imdb_languages'][0] not in self.languages:
                feed.reject(entry, 'primary language not in %s' % self.languages)
                continue

            # Reject some genrces outright
            if any(genre in self.imdb_genres_reject for genre in entry['imdb_genres']):
                feed.reject(entry, 'imdb genres')
                continue
            if any(genre in self.rt_genres_reject for genre in entry['rt_genres']):
                feed.reject(entry, 'rt genres')
                continue

            # Get the age classification of the movie
            entry_age = ''
            for years,age in sorted(self.max_accept_ages):
                if entry['rt_releases']['theater'] > datetime.now() - timedelta(days=(365*years)):
                    log.debug('Age class is %s' % age)
                    entry_age = age
                    break

            # Make sure all scores are reliable
            if entry['rt_critics_score'] < 0 or entry['rt_audience_score'] < 0 or entry['imdb_votes'] < self.min_imdb_votes or entry['imdb_score'] == 0:
                feed.reject(entry, 'Unreliable scores (rt_critics_consensus: %s, rt_critics_score: %s, rt_audience_score: %s, imdb_votes: %s, imdb_score: %s)' % 
                    (('filled' if entry['rt_critics_consensus'] else None) , entry['rt_critics_score'], entry['rt_audience_score'], entry['imdb_votes'], entry['imdb_score'])
                )
                continue

            # Score filters that depend on age
            score_offset = 0
            if entry_age == 'new' or entry_age == 'recent':
                pass
            elif entry_age == 'old':
                score_offset = -3;
            elif entry_age == 'older':
                score_offset = -5;
            elif entry_age == 'classic':
                score_offset = -12;
                if entry['rt_critics_rating'] != 'Certified Fresh':
                    reasons.append('%s movie (%s != Certified Fresh)' % (entry_age, entry['rt_critics_rating']))
            else:
                feed.reject(entry, 'Theater release date too far in the past')
                continue

            log.debug('Minimum acceptable score is %s' % self.global_min_score)

            # Determine which score to use
            if not entry['rt_critics_consensus'] and entry['rt_critics_rating'] != 'Certified Fresh':
                log.debug('No critics consensus, averaging audience with imdb')
                score = (entry['rt_audience_score'] + entry['imdb_score']*10)/2
            elif entry['rt_audience_rating'] == 'Spilled':
                log.debug('Audience doesn\'t approve, using audience score')
                score = entry['rt_audience_score']
            elif entry['rt_critics_score'] - entry['rt_audience_score'] > 20:
                log.debug('Critics and audience don\'t agree, using critics')
                score = entry['rt_critics_score']
            elif entry['rt_audience_score'] - entry['rt_critics_score'] > 20:
                log.debug('Critics and audience don\'t agree, using audience')
                score = entry['rt_audience_score']
            else:
                score = entry['rt_average_score']
                
            log.debug('Using score: %s' % score)
            if score_offset != 0:
                score = score + score_offset
                log.debug('Score offset used, score is now: %s' % score)

            if score < self.global_min_score:
                reasons.append('%s movie (score %s < %s)' % (entry_age, score, self.global_min_score))

            # A bunch of imdb genre filters
            strict_reasons = []
            allow_force_accept = not any(genre in self.imdb_genres_accept_except for genre in entry['imdb_genres'])
            if any(genre in self.imdb_genres_strict for genre in entry['imdb_genres']) and entry['rt_critics_rating'] != 'Certified Fresh':
                strict_reasons.append('not certified fresh')
            for genre in entry['imdb_genres']:
                if len(entry['imdb_genres']) == 1 or all(genre in self.imdb_single_genres_strict for genre in entry['imdb_genres']):
                    min_score = self.imdb_single_genres_strict.get(genre, None)
                    if min_score and score < min_score:
                            reasons.append('imdb single genre strict (%s and %s < %s)' % (genre, score, min_score))
                min_score = self.imdb_genres_strict.get(genre, None)
                if min_score and score < min_score:
                        strict_reasons.append('%s and %s < %s' % (genre, score, min_score))
                if allow_force_accept:
                    min_score = self.imdb_genres_accept.get(genre, None)
                    if min_score:
                        if not any(genre in self.imdb_genres_strict for genre in entry['imdb_genres']):
                            min_score = min_score - 5
                        if score > min_score:
                            log.debug('Accepting because of imdb genre accept (%s and %s > %s)' % (genre,score, min_score))
                            force_accept = True
                            break
            if strict_reasons:
                reasons.append('imdb genre strict (%s)' %  (', '.join(strict_reasons)))

            # A bunch of rt genre filters
            strict_reasons = []
            for genre in self.rt_genres_ignore[:]:
                if genre in entry['rt_genres']:
                    entry['rt_genres'].remove(genre)
            allow_force_accept = not any(genre in self.rt_genres_accept_except for genre in entry['rt_genres'])
            if any(genre in self.rt_genres_strict for genre in entry['rt_genres']) and entry['rt_critics_rating'] != 'Certified Fresh':
                strict_reasons.append('not certified fresh')
            for genre in entry['rt_genres']:
                if len(entry['rt_genres']) == 1 or all(genre in self.rt_single_genres_strict for genre in entry['rt_genres']):
                    min_score = self.rt_single_genres_strict.get(genre, None)
                    if min_score and score < min_score:
                            reasons.append('rt single genre strict (%s and %s < %s)' % (genre,score, min_score))
                min_score = self.rt_genres_strict.get(genre, None)
                if min_score and score < min_score:
                        strict_reasons.append('%s and %s < %s' % (genre, score, min_score))
                if allow_force_accept:
                    min_score = self.rt_genres_accept.get(genre, None)
                    if min_score:
                        if not any(genre in self.rt_genres_strict for genre in entry['rt_genres']):
                            min_score = min_score - 5
                        if score > min_score:
                            log.debug('Accepting because of rt genre accept (%s and %s > %s)' % (genre,score, min_score))
                            force_accept = True
                            break
            if strict_reasons:
                reasons.append('rt genre strict (%s)' %  (', '.join(strict_reasons)))


            if reasons and not force_accept:
                msg = 'Didn\'t accept `%s` because of rule(s) %s' % \
                    (entry.get('rt_name', None) or entry['title'], ', '.join(reasons))
                if feed.manager.options.debug:
                    log.debug(msg)
                else:
                    if score_offset != 0:
                        msg = 'Offset score by %s. %s' % (score_offset, msg)
                    if feed.manager.options.quiet:
                        log_once(msg, log)
                    else:
                        log.info(msg)
            else:
                log.debug('Accepting %s' % (entry['title']))
                feed.accept(entry)


register_plugin(MyMovieFilter, 'my_movie_filter', api_ver=2)