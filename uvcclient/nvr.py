#!/usr/bin/env python
#
#   Copyright 2015 Dan Smith (dsmith+uvc@danplanet.com)
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, either version 3 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.

import json
import logging
import pprint
import os
import sys
import zlib

# Python3 compatibility
try:
    import httplib
except ImportError:
    from http import client as httplib

try:
    import urlparse
except ImportError:
    import urllib.parse as urlparse


class Invalid(Exception):
    pass


class NotAuthorized(Exception):
    pass


class NvrError(Exception):
    pass

class CameraConnectionError(Exception):
    pass


class UVCRemote(object):
    """Remote control client for Ubiquiti Unifi Video NVR."""
    CHANNEL_NAMES = ['high', 'medium', 'low']

    def __init__(self, host, port, apikey, path='/', ssl=False):
        self._host = host
        self._port = port
        self._path = path
        self._ssl = ssl
        if path != '/':
            raise Invalid('Path not supported yet')
        self._apikey = apikey
        self._log = logging.getLogger('UVC(%s:%s)' % (host, port))
        self._bootstrap = self._get_bootstrap()
        version = '.'.join(str(x) for x in self.server_version)
        self._log.debug('Server version is %s' % version)

    @property
    def server_version(self):
        version = self._bootstrap['systemInfo']['version'].split('.')
        major = int(version[0])
        minor = int(version[1])
        try:
            rev = int(version[2])
        except ValueError:
            rev = 0
        return (major, minor, rev)

    @property
    def camera_identifier(self):
        if self.server_version >= (3, 2, 0):
            return 'id'
        else:
            return 'uuid'

    def _get_http_connection(self):
        if self._ssl:
            return httplib.HTTPSConnection(self._host, self._port)
        else:
            return httplib.HTTPConnection(self._host, self._port)

    def _safe_request(self, *args, **kwargs):
        try:
            conn = self._get_http_connection()
            conn.request(*args, **kwargs)
            return conn.getresponse()
        except OSError:
            raise CameraConnectionError('Unable to contact camera')
        except httplib.HTTPException as ex:
            raise CameraConnectionError('Error connecting to camera: %s' % (
                str(ex)))

    def _uvc_request(self, *args, **kwargs):
        try:
            return self._uvc_request_safe(*args, **kwargs)
        except OSError:
            raise NvrError('Failed to contact NVR')
        except httplib.HTTPException as ex:
            raise NvrError('Error connecting to camera: %s' % str(ex))

    def _uvc_request_safe(self, path, method='GET', data=None,
                          mimetype='application/json'):
        conn = self._get_http_connection()
        if '?' in path:
            url = '%s&apiKey=%s' % (path, self._apikey)
        else:
            url = '%s?apiKey=%s' % (path, self._apikey)

        headers = {
            'Content-Type': mimetype,
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Encoding': 'gzip, deflate, sdch',
        }
        self._log.debug('%s %s headers=%s data=%s' % (
            method, url, headers, repr(data)))
        conn.request(method, url, data, headers)
        resp = conn.getresponse()
        headers = dict(resp.getheaders())
        self._log.debug('%s %s Result: %s %s' % (method, url, resp.status,
                                                 resp.reason))
        if resp.status in (401, 403):
            raise NotAuthorized('NVR reported authorization failure')
        if resp.status / 100 != 2:
            raise NvrError('Request failed: %s' % resp.status)

        data = resp.read()
        if (headers.get('content-encoding') == 'gzip' or
                headers.get('Content-Encoding') == 'gzip'):
            data = zlib.decompress(data, 32 + zlib.MAX_WBITS)
        return json.loads(data.decode())

    def _get_bootstrap(self):
        return self._uvc_request('/api/2.0/bootstrap')['data'][0]

    def dump(self, uuid):
        """Dump information for a camera by UUID."""
        data = self._uvc_request('/api/2.0/camera/%s' % uuid)
        pprint.pprint(data)

    def get_enablestatusled(self, uuid):
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)
        return data['data'][0]['enableStatusLed']

    def set_enablestatusled(self, uuid, mode):
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)
        mode = mode.lower()
        if mode == 'true':
            data['data'][0]['enableStatusLed'] = True
        elif mode == 'false':
            data['data'][0]['enableStatusLed'] = False
        else:
            raise Invalid('Unknown mode')

        data = self._uvc_request(url, 'PUT', json.dumps(data['data'][0]))
        updated = data['data'][0]['enableStatusLed']
        return data == updated

    def get_enablesuggestedvideosettings(self, uuid):
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)
        return data['data'][0]['enableSuggestedVideoSettings']

    def set_enablesuggestedvideosettings(self, uuid, mode):
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)
        mode = mode.lower()
        if mode == 'true':
            data['data'][0]['enableSuggestedVideoSettings'] = True
        elif mode == 'false':
            data['data'][0]['enableSuggestedVideoSettings'] = False
        else:
            raise Invalid('Unknown mode')

        data = self._uvc_request(url, 'PUT', json.dumps(data['data'][0]))
        updated = data['data'][0]['enableSuggestedVideoSettings']
        return data == updated

    def get_firmwareBuild(self, uuid):
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)
        return data['data'][0]['firmwareBuild']

    def get_firmwareVersion(self, uuid):
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)
        return data['data'][0]['firmwareVersion']

    def get_hasDefaultCredentials(self, uuid):
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)
        return data['data'][0]['hasDefaultCredentials']

    def get_cameramacaddress(self, uuid):
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)
        return data['data'][0]['mac']

    def get_iscameramanagedbynvr(self, uuid):
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)
        return data['data'][0]['managed']

    def get_cameramicvolume(self, uuid):
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)
        return data['data'][0]['micVolume']

    def set_cameramicvolume(self, uuid, volume):
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)
        data['data'][0]['micVolume'] = volume

        data = self._uvc_request(url, 'PUT', json.dumps(data['data'][0]))
        updated = data['data'][0]['micVolume']
        return data == updated

    def get_cameramodel(self, uuid):
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)
        return data['data'][0]['model']

    def get_cameraplatform(self, uuid):
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)
        return data['data'][0]['platform']

    def get_cameraipaddress(self, uuid):
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)
        return data['data'][0]['host']

    def get_recordprepaddingtime(self, uuid):
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)
        recmodes = data['data'][0]['recordingSettings']
        return recmodes['prePaddingSecs']

    def set_recordprepaddingtime(self, uuid, seconds):
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)

        settings = data['data'][0]['recordingSettings']
        settings['prePaddingSecs'] = seconds

        data = self._uvc_request(url, 'PUT', json.dumps(data['data'][0]))
        updated = data['data'][0]['recordingSettings']
        return data == updated

    def get_recordpostpaddingtime(self, uuid):
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)
        recmodes = data['data'][0]['recordingSettings']
        return recmodes['postPaddingSecs']

    def set_recordpostpaddingtime(self, uuid, seconds):
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)

        settings = data['data'][0]['recordingSettings']
        settings['postPaddingSecs'] = seconds

        data = self._uvc_request(url, 'PUT', json.dumps(data['data'][0]))
        updated = data['data'][0]['recordingSettings']
        return data == updated

    def get_cameratimezone(self, uuid):
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)
        recmodes = data['data'][0]['deviceSettings']
        return recmodes['timezone']

    def get_externalirmode(self, uuid):
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)
        camerasettings = data['data'][0]['ispSettings']
        if camerasettings['enableExternalIr'] == 0:
            return 'off'
        elif camerasettings['enableExternalIr'] == 1:
            return 'on'
        else:
            return 'unknown'

    def set_externalirmode(self, uuid, mode):
        """Turn off or on the external ir emitter for a camera by UUID.

        :param uuid: Camera UUID
        :param mode: One of on or off
        :returns: True if successful, False or None otherwise
        """
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)
        settings = data['data'][0]['ispSettings']
        mode = mode.lower()
        if mode == 'off':
            settings['enableExternalIr'] = 0
        elif mode == 'on':
            settings['enableExternalIr'] = 1
        else:
            raise Invalid('Unknown mode')

        data = self._uvc_request(url, 'PUT', json.dumps(data['data'][0]))
        updated = data['data'][0]['ispSettings']
        return settings == updated

    def get_showosddatemode(self, uuid):
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)
        camerasettings = data['data'][0]['osdSettings']
        if camerasettings['enableDate'] == 0:
            return 'off'
        elif camerasettings['enableDate'] == 1:
            return 'on'
        else:
            return 'unknown'

    def set_showosddatemode(self, uuid, mode):
        """Turn off or on the on screen display of the date for the camera by UUID.

        :param uuid: Camera UUID
        :param mode: One of on or off
        :returns: True if successful, False or None otherwise
        """
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)
        settings = data['data'][0]['osdSettings']
        mode = mode.lower()
        if mode == 'off':
            settings['enableDate'] = 0
        elif mode == 'on':
            settings['enableDate'] = 1
        else:
            raise Invalid('Unknown mode')

        data = self._uvc_request(url, 'PUT', json.dumps(data['data'][0]))
        updated = data['data'][0]['osdSettings']
        return settings == updated

    def get_showosdlogomode(self, uuid):
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)
        camerasettings = data['data'][0]['osdSettings']
        if camerasettings['enableLogo'] == 0:
            return 'off'
        elif camerasettings['enableLogo'] == 1:
            return 'on'
        else:
            return 'unknown'

    def set_showosdlogomode(self, uuid, mode):
        """Turn off or on the on screen display of the cameraname for the camera by UUID.

        :param uuid: Camera UUID
        :param mode: One of on or off
        :returns: True if successful, False or None otherwise
        """
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)
        settings = data['data'][0]['osdSettings']
        mode = mode.lower()
        if mode == 'off':
            settings['enableLogo'] = 0
        elif mode == 'on':
            settings['enableLogo'] = 1
        else:
            raise Invalid('Unknown mode')

        data = self._uvc_request(url, 'PUT', json.dumps(data['data'][0]))
        updated = data['data'][0]['osdSettings']
        return settings == updated

    def get_brightness(self, uuid):
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)
        camerasettings = data['data'][0]['ispSettings']
        return camerasettings['brightness']

    def set_brightness(self, uuid, level):
        """Set the brightness level the recording will use for the camera by UUID.

        :param uuid: Camera UUID
        :param level: 0-100
        :returns: True if successful, False or None otherwise
        """
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)

        settings = data['data'][0]['ispSettings']
        settings['brightness'] = level

        data = self._uvc_request(url, 'PUT', json.dumps(data['data'][0]))
        updated = data['data'][0]['ispSettings']

    def get_irbrightness(self, uuid):
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)
        camerasettings = data['data'][0]['ispSettings']
        return camerasettings['irOnValBrightness']

    def set_irbrightness(self, uuid, level):
        """Set the brightness level the recording when IR is active for the camera by UUID.

        :param uuid: Camera UUID
        :param level: 0-100
        :returns: True if successful, False or None otherwise
        """
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)

        settings = data['data'][0]['ispSettings']
        settings['irOnValBrightness'] = level

        data = self._uvc_request(url, 'PUT', json.dumps(data['data'][0]))
        updated = data['data'][0]['irOnValBrightness']

    def get_contrast(self, uuid):
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)
        camerasettings = data['data'][0]['ispSettings']
        return camerasettings['contrast']

    def set_contrast(self, uuid, level):
        """Set the contrast level the recording will use for the camera by UUID.

        :param uuid: Camera UUID
        :param level: 0-100
        :returns: True if successful, False or None otherwise
        """
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)

        settings = data['data'][0]['ispSettings']
        settings['contrast'] = level

        data = self._uvc_request(url, 'PUT', json.dumps(data['data'][0]))
        updated = data['data'][0]['contrast']

    def get_ircontrast(self, uuid):
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)
        camerasettings = data['data'][0]['ispSettings']
        return camerasettings['irOnValContrast']

    def set_ircontrast(self, uuid, level):
        """Set the contrast level the recording when IR is active for the camera by UUID.

        :param uuid: Camera UUID
        :param level: 0-100
        :returns: True if successful, False or None otherwise
        """
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)

        settings = data['data'][0]['ispSettings']
        settings['irOnValContrast'] = level

        data = self._uvc_request(url, 'PUT', json.dumps(data['data'][0]))
        updated = data['data'][0]['irOnValContrast']

    def get_denoise(self, uuid):
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)
        camerasettings = data['data'][0]['ispSettings']
        return camerasettings['denoise']

    def set_denoise(self, uuid, level):
        """Set the denoise level the recording will use for the camera by UUID.

        :param uuid: Camera UUID
        :param level: 0-100
        :returns: True if successful, False or None otherwise
        """
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)

        settings = data['data'][0]['ispSettings']
        settings['denoise'] = level

        data = self._uvc_request(url, 'PUT', json.dumps(data['data'][0]))
        updated = data['data'][0]['denoise']

    def get_irdenoise(self, uuid):
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)
        camerasettings = data['data'][0]['ispSettings']
        return camerasettings['irOnValDenoise']

    def set_irdenoise(self, uuid, level):
        """Set the denoise level the recording when IR is active for the camera by UUID.

        :param uuid: Camera UUID
        :param level: 0-100
        :returns: True if successful, False or None otherwise
        """
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)

        settings = data['data'][0]['ispSettings']
        settings['irOnValDenoise'] = level

        data = self._uvc_request(url, 'PUT', json.dumps(data['data'][0]))
        updated = data['data'][0]['irOnValDenoise']

    def get_hue(self, uuid):
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)
        camerasettings = data['data'][0]['ispSettings']
        return camerasettings['hue']

    def set_hue(self, uuid, level):
        """Set the hue level the recording will use for the camera by UUID.

        :param uuid: Camera UUID
        :param level: 0-100
        :returns: True if successful, False or None otherwise
        """
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)

        settings = data['data'][0]['ispSettings']
        settings['hue'] = level

        data = self._uvc_request(url, 'PUT', json.dumps(data['data'][0]))
        updated = data['data'][0]['hue']

    def get_irhue(self, uuid):
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)
        camerasettings = data['data'][0]['ispSettings']
        return camerasettings['irOnValHue']

    def set_irhue(self, uuid, level):
        """Set the hue level the recording when IR is active for the camera by UUID.

        :param uuid: Camera UUID
        :param level: 0-100
        :returns: True if successful, False or None otherwise
        """
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)

        settings = data['data'][0]['ispSettings']
        settings['irOnValHue'] = level

        data = self._uvc_request(url, 'PUT', json.dumps(data['data'][0]))
        updated = data['data'][0]['irOnValHue']

    def get_saturation(self, uuid):
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)
        camerasettings = data['data'][0]['ispSettings']
        return camerasettings['saturation']

    def set_saturation(self, uuid, level):
        """Set the saturation level the recording will use for the camera by UUID.

        :param uuid: Camera UUID
        :param level: 0-100
        :returns: True if successful, False or None otherwise
        """
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)

        settings = data['data'][0]['ispSettings']
        settings['saturation'] = level

        data = self._uvc_request(url, 'PUT', json.dumps(data['data'][0]))
        updated = data['data'][0]['saturation']

    def get_irsaturation(self, uuid):
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)
        camerasettings = data['data'][0]['ispSettings']
        return camerasettings['irOnValSaturation']

    def set_irsaturation(self, uuid, level):
        """Set the saturation level the recording when IR is active for the camera by UUID.

        :param uuid: Camera UUID
        :param level: 0-100
        :returns: True if successful, False or None otherwise
        """
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)

        settings = data['data'][0]['ispSettings']
        settings['irOnValSaturation'] = level

        data = self._uvc_request(url, 'PUT', json.dumps(data['data'][0]))
        updated = data['data'][0]['irOnValSaturation']

    def get_sharpness(self, uuid):
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)
        camerasettings = data['data'][0]['ispSettings']
        return camerasettings['sharpness']

    def set_sharpness(self, uuid, level):
        """Set the sharpness level the recording will use for the camera by UUID.

        :param uuid: Camera UUID
        :param level: 0-100
        :returns: True if successful, False or None otherwise
        """
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)

        settings = data['data'][0]['ispSettings']
        settings['sharpness'] = level

        data = self._uvc_request(url, 'PUT', json.dumps(data['data'][0]))
        updated = data['data'][0]['sharpness']

    def get_irsharpness(self, uuid):
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)
        camerasettings = data['data'][0]['ispSettings']
        return camerasettings['irOnValSharpness']

    def set_irsharpness(self, uuid, level):
        """Set the sharpness level the recording when IR is active for the camera by UUID.

        :param uuid: Camera UUID
        :param level: 0-100
        :returns: True if successful, False or None otherwise
        """
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)

        settings = data['data'][0]['ispSettings']
        settings['irOnValSharpness'] = level

        data = self._uvc_request(url, 'PUT', json.dumps(data['data'][0]))
        updated = data['data'][0]['irOnValSharpness']

    def get_wdr(self, uuid):
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)
        camerasettings = data['data'][0]['ispSettings']
        return camerasettings['wdr']

    def set_wdr(self, uuid, level):
        """Set the wdr level the recording will use for the camera by UUID.

        :param uuid: Camera UUID
        :param level: 0-100
        :returns: True if successful, False or None otherwise
        """
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)

        settings = data['data'][0]['ispSettings']
        settings['wdr'] = level

        data = self._uvc_request(url, 'PUT', json.dumps(data['data'][0]))
        updated = data['data'][0]['wdr']

    def get_lensdistortioncorrectionmode(self, uuid):
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)
        camerasettings = data['data'][0]['ispSettings']
        if camerasettings['lensDistortionCorrection'] == 0:
            return 'off'
        elif camerasettings['lensDistortionCorrection'] == 1:
            return 'on'
        else:
            return 'unknown'

    def set_lensdistortioncorrectionmode(self, uuid, mode):
        """Turn off or on the correction of lens distortion for the camera by UUID.

        :param uuid: Camera UUID
        :param mode: One of on or off
        :returns: True if successful, False or None otherwise
        """
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)
        settings = data['data'][0]['ispSettings']
        mode = mode.lower()
        if mode == 'off':
            settings['lensDistortionCorrection'] = 0
        elif mode == 'on':
            settings['lensDistortionCorrection'] = 1
        else:
            raise Invalid('Unknown mode')

        data = self._uvc_request(url, 'PUT', json.dumps(data['data'][0]))
        updated = data['data'][0]['ispSettings']
        return settings == updated

    def get_aemode(self, uuid):
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)
        camerasettings = data['data'][0]['ispSettings']
        if (camerasettings['aemode'] == "auto"):
            return 'normal'
        elif (camerasettings['aemode'] == "flick50"):
            return 'anti-flicker for 50hz light'
        elif (camerasettings['aemode'] == "flick60"):
            return 'anti-flicker for 60hz light'
        else:
            return 'unknown'

    def set_aemode(self, uuid, mode):
        """set the aemode for the camera by UUID.

        :param uuid: Camera UUID
        :param mode: One of normal, antiflicker50hz, or antiflicker60hz
        :returns: True if successful, False or None otherwise
        """
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)
        settings = data['data'][0]['ispSettings']
        mode = mode.lower()
        if mode == 'normal':
            settings['aemode'] = "auto"
        elif mode == 'antiflicker50hz':
            settings['aemode'] = "flick50"
        elif mode == 'antiflicker60hz':
            settings['aemode'] = "flick60"
        else:
            raise Invalid('Unknown mode')

        data = self._uvc_request(url, 'PUT', json.dumps(data['data'][0]))
        updated = data['data'][0]['ispSettings']
        return settings == updated

    def get_aggressiveantiflicker(self, uuid):
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)
        camerasettings = data['data'][0]['ispSettings']
        if (camerasettings['aggressiveAntiFlicker'] == 0):
            return 'disabled'
        elif (camerasettings['aggressiveAntiFlicker'] == 1):
            return 'enabled'
        else:
            return 'unknown'

    def set_aggressiveantiflicker(self, uuid, mode):
        """set the antiflicker mode for the camera by UUID.
        only applies if aemode is anti-flicker 50hz or anti-flicker
        60hz

        :param uuid: Camera UUID
        :param mode: One of enabled or disabledz
        :returns: True if successful, False or None otherwise
        """
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)
        settings = data['data'][0]['ispSettings']
        mode = mode.lower()
        if mode == 'disabled':
            settings['aggressiveAntiFlicker'] = 0
        elif mode == 'enabled':
            settings['aggressiveAntiFlicker'] = 1
        else:
            raise Invalid('Unknown mode')

        data = self._uvc_request(url, 'PUT', json.dumps(data['data'][0]))
        updated = data['data'][0]['ispSettings']
        return settings == updated

    def get_orientation(self, uuid):
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)
        camerasettings = data['data'][0]['ispSettings']
        if (camerasettings['flip'] == 0 and
            camerasettings['mirror'] == 0):
            return 'normal'
        elif (camerasettings['flip'] == 0 and
            camerasettings['mirror'] == 1):
            return 'flip horizontally'
        elif (camerasettings['flip'] == 1 and
            camerasettings['mirror'] == 0):
            return 'flip vertically'
        elif (camerasettings['flip'] == 1 and
            camerasettings['mirror'] == 1):
            return 'flip both horizontally and vertically'
        else:
            return 'unknown'

    def get_irsensitivity(self, uuid):
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)
        camerasettings = data['data'][0]['ispSettings']
        if camerasettings['icrSensitivity'] == 0:
            return 'low'
        elif camerasettings['icrSensitivity'] == 1:
            return 'medium'
        elif camerasettings['icrSensitivity'] == 2:
            return 'high'
        else:
            return 'unknown'

    def set_irsensitivity(self, uuid, level):
        """Set the IR camera sensitvity for a camera by UUID.

        :param uuid: Camera UUID
        :param mode: One of low, medium, or high
        :returns: True if successful, False or None otherwise
        """
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)
        settings = data['data'][0]['ispSettings']
        level = level.lower()
        if level == 'low':
            settings['icrSensitivity'] = 0
        elif level == 'medium':
            settings['icrSensitivity'] = 1
        elif level == 'high':
            settings['icrSensitivity'] = 2
        else:
            raise Invalid('Unknown mode')

        data = self._uvc_request(url, 'PUT', json.dumps(data['data'][0]))
        updated = data['data'][0]['ispSettings']
        return settings == updated

    def get_irledmode(self, uuid):
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)
        irledmodes = data['data'][0]['ispSettings']
        if irledmodes['irLedMode'] == "auto":
            return 'auto'
        elif (irledmodes['irLedMode'] == "manual" and
                irledmodes['irLedLevel'] == 0):
            return 'off'
        elif (irledmodes['irLedMode'] == "manual" and
                irledmodes['irLedLevel'] > 0):
            return 'on'
        else:
            return 'unknown'

    def set_irledmode(self, uuid, mode):
        """Set the IR viewing mode for a camera by UUID.

        :param uuid: Camera UUID
        :param mode: One of on, off, or auto
        :returns: True if successful, False or None otherwise
        """
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)
        settings = data['data'][0]['ispSettings']
        mode = mode.lower()
        if mode == 'off':
            settings['irLedLevel'] = 0
            settings['irLedMode'] = "manual"
        elif mode == 'on':
            settings['irLedLevel'] = 215
            settings['irLedMode'] = "manual"
        elif mode == 'auto':
            settings['irLedLevel'] = 215
            settings['irLedMode'] = "auto"
        else:
            raise Invalid('Unknown mode')

        data = self._uvc_request(url, 'PUT', json.dumps(data['data'][0]))
        updated = data['data'][0]['ispSettings']
        return settings == updated

    def get_picture_settings(self, uuid):
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)
        return data['data'][0]['ispSettings']

    def set_picture_settings(self, uuid, settings):
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)
        for key in settings:
            dtype = type(data['data'][0]['ispSettings'][key])
            try:
                data['data'][0]['ispSettings'][key] = dtype(settings[key])
            except ValueError:
                raise Invalid('Setting `%s\' requires %s not %s' % (
                    key, dtype.__name__, type(settings[key]).__name__))
        data = self._uvc_request(url, 'PUT', json.dumps(data['data'][0]))
        return data['data'][0]['ispSettings']

    def prune_zones(self, uuid):
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)
        data['data'][0]['zones'] = [data['data'][0]['zones'][0]]
        self._uvc_request(url, 'PUT', json.dumps(data['data'][0]))

    def list_zones(self, uuid):
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)
        return data['data'][0]['zones']

    def index(self):
        """Return an index of available cameras.

        :returns: A list of dictionaries with keys of name, uuid
        """
        cams = self._uvc_request('/api/2.0/camera')['data']
        return [{'name': x['name'],
                 'uuid': x['uuid'],
                 'state': x['state'],
                 'managed': x['managed'],
                 'id': x['_id'],
             } for x in cams if not x['deleted']]

    def get_camera(self, uuid):
        return self._uvc_request('/api/2.0/camera/%s' % uuid)['data'][0]

    def get_snapshot(self, uuid):
        url = '/api/2.0/snapshot/camera/%s?force=true&apiKey=%s' % (
            uuid, self._apikey)
        print(url)
        resp = self._safe_request('GET', url)
        if resp.status != 200:
            raise NvrError('Snapshot returned %i' % resp.status)
        return resp.read()

    def get_recordmode(self, uuid):
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)
        recmodes = data['data'][0]['recordingSettings']
        if recmodes['fullTimeRecordEnabled']:
            return 'full'
        elif recmodes['motionRecordEnabled']:
            return 'motion'
        else:
            return 'none'

    def set_recordmode(self, uuid, mode, chan=None):
        """Set the recording mode for a camera by UUID.

        :param uuid: Camera UUID
        :param mode: One of none, full, or motion
        :param chan: One of the values from CHANNEL_NAMES
        :returns: True if successful, False or None otherwise
        """
        self.dump(uuid)
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)

        settings = data['data'][0]['recordingSettings']
        mode = mode.lower()
        if mode == 'none':
            settings['fullTimeRecordEnabled'] = False
            settings['motionRecordEnabled'] = False
        elif mode == 'full':
            settings['fullTimeRecordEnabled'] = True
            settings['motionRecordEnabled'] = False
        elif mode == 'motion':
            settings['fullTimeRecordEnabled'] = False
            settings['motionRecordEnabled'] = True
        else:
            raise Invalid('Unknown mode')

        if chan:
            settings['channel'] = self.CHANNEL_NAMES.index(chan)
            changed = data['data'][0]['recordingSettings']

        data = self._uvc_request(url, 'PUT', json.dumps(data['data'][0]))
        updated = data['data'][0]['recordingSettings']
        return settings == updated

    def get_enablestatusled(self, uuid):
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)
        return data['data'][0]['enableStatusLed']

    def set_enablestatusled(self, uuid, state):
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)
        state = state.lower()
        if state == 'true':
            data['data'][0]['enableStatusLed'] = True
        elif state == 'false':
            data['data'][0]['enableStatusLed'] = False
        else:
            raise Invalid('Unknown mode')

        data = self._uvc_request(url, 'PUT', json.dumps(data['data'][0]))
        updated = data['data'][0]['enableStatusLed']
        return data == updated

    def get_enablesuggestedvideosettings(self, uuid):
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)
        return data['data'][0]['enableSuggestedVideoSettings']

    def set_enablesuggestedvideosettings(self, uuid, state):
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)
        state = state.lower()
        if state == 'true':
            data['data'][0]['enableSuggestedVideoSettings'] = True
        elif state == 'false':
            data['data'][0]['enableSuggestedVideoSettings'] = False
        else:
            raise Invalid('Unknown mode')

        data = self._uvc_request(url, 'PUT', json.dumps(data['data'][0]))
        updated = data['data'][0]['enableSuggestedVideoSettings']
        return data == updated

    def set_enablesuggestedvideosettings(self, uuid, state):
        url = '/api/2.0/camera/%s' % uuid
        data = self._uvc_request(url)
        state = state.lower()
        if state == 'true':
            data['data'][0]['enableSuggestedVideoSettings'] = True
        elif state == 'false':
            data['data'][0]['enableSuggestedVideoSettings'] = False
        else:
            raise Invalid('Unknown mode')

        data = self._uvc_request(url, 'PUT', json.dumps(data['data'][0]))
        updated = data['data'][0]['enableSuggestedVideoSettings']
        return data == updated

    def name_to_uuid(self, name):
        """Attempt to convert a camera name to its UUID.

        :param name: Camera name
        :returns: The UUID of the first camera with the same name if found,
                  otherwise None. On v3.2.0 and later, returns id.
        """
        cameras = self.index()
        if self.server_version >= (3, 2, 0):
            cams_by_name = {x['name']: x['id'] for x in cameras}
        else:
            cams_by_name = {x['name']: x['uuid'] for x in cameras}
        return cams_by_name.get(name)

    def test_login(self, username, password):
        headers = {'Content-Type': 'application/json'}
        data = json.dumps({'username': username,
                           'password': password})
        resp = self._safe_request('POST', '/api/2.0/login', data,
                                  headers=headers)
        return resp


def get_auth_from_env():
    """Attempt to get UVC NVR connection information from the environment.

    Supports either a combined variable called UVC formatted like:

        UVC="http://192.168.1.1:7080/?apiKey=XXXXXXXX"

    or individual ones like:

        UVC_HOST=192.168.1.1
        UVC_PORT=7080
        UVC_APIKEY=XXXXXXXXXX

    :returns: A tuple like (host, port, apikey, path)
    """

    combined = os.getenv('UVC')
    if combined:
        # http://192.168.1.1:7080/apikey
        result = urlparse.urlparse(combined)
        if ':' in result.netloc:
            host, port = result.netloc.split(':', 1)
            port = int(port)
        else:
            host = result.netloc
            port = 7080
        apikey = urlparse.parse_qs(result.query)['apiKey'][0]
        path = result.path
    else:
        host = os.getenv('UVC_HOST')
        port = int(os.getenv('UVC_PORT', 7080))
        apikey = os.getenv('UVC_APIKEY')
        path = '/'
    return host, port, apikey, path
