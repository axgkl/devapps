from datetime import datetime
import time


class times:
    months = {
        '01': 'Jan',
        '02': 'Feb',
        '03': 'Mar',
        '04': 'Apr',
        '05': 'May',
        '06': 'Jun',
        '07': 'Jul',
        '08': 'Aug',
        '09': 'Sep',
        '10': 'Oct',
        '11': 'Nov',
        '12': 'Dec',
    }
    units = {'s': 1, 'h': 3600, 'd': 86400, 'w': 86400 * 7, 'm': 86400 * 7 * 31}
    units['y'] = units['d'] * 365
    now = time.time
    utcnow = lambda: datetime.utcnow().timestamp()
    millis = lambda sec=-1: int(times.utcnow() if sec == -1 else sec) * 1000

    def dt_human(since, full_date=0):
        """Returns e.g. "1h" for since a unixtime or isotime"""
        since, dt, h = times.dt_human_nf(since)
        if full_date and dt > full_date:
            d = time.ctime(since).rsplit(' ', 2)[0]
            h += f' ({d})'
        return h

    def dt_human_nf(since):
        if isinstance(since, str):
            since = times.iso_to_unix(since)
        dt = times.utcnow() - since
        if dt < 61:
            return since, dt, '%ss' % int(dt)
        if dt < 3600:
            return since, dt, '%sm' % int(dt / 60)
        if dt < 86400:
            return since, dt, '%sh' % int(dt / 3600)

        if dt < 86400 * 60:
            return since, dt, '%sd' % int(dt / 86400)
        return since, dt, '%sM' % round(dt / 86400 / 30, 1)

    def to_sec(s):
        """ "1h" -> 3600, "10" -> 10"""
        u, o = times.units.get(s[-1]), 1
        if u is None:
            u, o = 1, 0
        return int(s[:-o]) * u

    def iso_to_unix(s):
        nanos = ''
        if '.' in s:
            nanos = '.%f'
        if s[-1] == 'Z':
            return time.mktime(time.strptime(s, f'%Y-%m-%dT%H:%M:%S{nanos}Z'))
        # +0200 at the end:
        return time.mktime(time.strptime(s, f'%Y-%m-%dT%H:%M:%S{nanos}%z'))
