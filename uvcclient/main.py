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

import getpass
import logging
import optparse
import sys
import pprint

from uvcclient import nvr
from uvcclient import camera
from uvcclient import store

INFO_STORE = store.get_info_store()


def do_led(camera_info, enabled):
    password = INFO_STORE.get_camera_password(camera_info['uuid']) or 'ubnt'
    cam_client = camera.UVCCameraClient(camera_info['host'],
                                        camera_info['username'],
                                        password)
    cam_client.login()
    cam_client.set_led(enabled)


def do_snapshot(client, camera_info):
    password = INFO_STORE.get_camera_password(camera_info['uuid']) or 'ubnt'
    if client.server_version >= (3, 2, 0):
        cam_client = camera.UVCCameraClientV320(camera_info['host'],
                                                camera_info['username'],
                                                password)
    else:
        cam_client = camera.UVCCameraClient(camera_info['host'],
                                            camera_info['username'],
                                            password)
    try:
        cam_client.login()
        return cam_client.get_snapshot()
    except (camera.CameraAuthError, camera.CameraConnectError):
        # Fall back to proxy through the NVR
        return client.get_snapshot(camera_info['uuid'])


def do_set_password(opts):
    print('This will store the administrator password for a camera ')
    print('for later use. It will be stored on disk obscured, but ')
    print('NOT ENCRYPTED! If this is not okay, cancel now.')
    print('')
    password1 = getpass.getpass('Password: ')
    password2 = getpass.getpass('Confirm: ')
    if password1 != password2:
        print('Passwords do not match')
        return
    INFO_STORE.set_camera_password(opts.uuid, password1)
    print('Password set')


def main():
    host, port, apikey, path = nvr.get_auth_from_env()

    parser = optparse.OptionParser()
    parser.add_option('-H', '--host', default=host,
                      help='UVC Hostname')
    parser.add_option('-P', '--port', default=port, type=int,
                      help='UVC Port')
    parser.add_option('-K', '--apikey', default=apikey,
                      help='UVC API Key')
    parser.add_option('-v', '--verbose', action='store_true', default=False)
    parser.add_option('-d', '--dump', action='store_true', default=False)
    parser.add_option('-u', '--uuid', default=None, help='Camera UUID')
    parser.add_option('--name', default=None, help='Camera name')
    parser.add_option('-l', '--list', action='store_true', default=False)
    parser.add_option('--irsensitivity', default=None,
                      help='IR Camera Sensitivity (low,medium,high)')
    parser.add_option('--irledmode', default=None,
                      help='IR Led mode (none,full,motion)')
    parser.add_option('--externalirmode', default=None,
                      help='Recording mode off, on)')
    parser.add_option('--recordmode', default=None,
                      help='Recording mode (none,full,motion)')
    parser.add_option('--get-externalirmode', default=None, action='store_true',
                      help='Show if an external IR emitter is on')
    parser.add_option('--get-irledmode', default=None, action='store_true',
                      help='Show IR detection mode')
    parser.add_option('--get-irsensitivity', default=None, action='store_true',
                      help='Show IR Camera sensitivity level')
    parser.add_option('--get-recordmode', default=None, action='store_true',
                      help='Show recording mode')
    parser.add_option('--recordchannel', default=None,
                      help='Recording channel (high,medium,low)')
    parser.add_option('-p', '--get-picture-settings', action='store_true',
                      default=False,
                      help='Return picture settings as a string')
    parser.add_option('--set-picture-settings',
                      default=None,
                      help=('Set picture settings with a string like that '
                            'returned from --get-picture-settings'))
    parser.add_option('--set-led', default=None, metavar='ENABLED',
                      help='Enable/Disable front LED (on,off)')
    parser.add_option('--get-snapshot', default=None, action='store_true',
                      help='Get a snapshot image and write to stdout')
    parser.add_option('--prune-zones', default=None, action='store_true',
                      help='Prune all but the first motion zone')
    parser.add_option('--list-zones', default=None, action='store_true',
                      help='List motion zones')
    parser.add_option('--set-password', default=None, action='store_true',
                      help='Store camera password')
    parser.add_option('--test-login', default=None, action='store_true',
                      help='Test if the given username/password can login to the NVR')
    parser.add_option('--username', default=None, help='Username to attempt the login with')
    parser.add_option('--password', default=None, help='Password to attempt the login with')
    parser.add_option('--get-allalerts', default=None, action='store_true',
                      help='Dump the alerts in the alert table')
    parser.add_option('--delete-allalerts', default=None, action='store_true',
                      help='Deletes all the alerts in the alert table')
    parser.add_option('--delete-alert', action='store_true',
                      help='Delete the alert identified by the timestamp or alert-type arguments')
    parser.add_option('--timestamp', type=int, help='integer timestamp to identify an alert')
    parser.add_option('--alert-type', default=None, help='type of alert to delete')

    opts, args = parser.parse_args()

    if not all([opts.host, opts.port, opts.apikey]):
        print('Host, port, and apikey are required')
        return

    if opts.verbose:
        level = logging.DEBUG
    else:
        level = logging.WARNING
    logging.basicConfig(level=level)

    client = nvr.UVCRemote(opts.host, opts.port, opts.apikey)

    if opts.name:
        opts.uuid = client.name_to_uuid(opts.name)
        if not opts.uuid:
            print('`%s\' is not a valid name' % opts.name)
            return

    if opts.dump:
        client.dump(opts.uuid)
    elif opts.list:
        for cam in client.index():
            ident = cam[client.camera_identifier]
            recmode = client.get_recordmode(ident)
            ip = client.get_cameraipaddress(ident)
            if not cam['managed']:
                status = 'new'
            elif cam['state'] == 'FIRMWARE_OUTDATED':
                status = 'outdated'
            elif cam['state'] == 'UPGRADING':
                status = 'upgrading'
            elif cam['state'] == 'DISCONNECTED':
                status = 'offline'
            elif cam['state'] == 'CONNECTED':
                status = 'online'
            else:
                status = 'unknown:%s' % cam['state']
            print('%s: %-24.24s %s [%10s] %s' % (cam['id'], cam['name'], ip, status, recmode))

    elif opts.recordmode:
        if not opts.uuid:
            print('Name or UUID is required')
            return 1

        r = client.set_recordmode(opts.uuid, opts.recordmode,
                                  opts.recordchannel)
        if r is True:
            return 0
        else:
            return 1
    elif opts.externalirmode:
        if not opts.uuid:
            print('Name or UUID is required')
            return 1

        r = client.set_externalirmode(opts.uuid, opts.externalirmode)
        if r is True:
            return 0
        else:
            return 1
    elif opts.irsensitivity:
        if not opts.uuid:
            print('Name or UUID is required')
            return 1

        r = client.set_irsensitivity(opts.uuid, opts.irsensitivity)
        if r is True:
            return 0
        else:
            return 1
    elif opts.irledmode:
        if not opts.uuid:
            print('Name or UUID is required')
            return 1

        r = client.set_irledmode(opts.uuid, opts.irledmode)
        if r is True:
            return 0
        else:
            return 1
    elif opts.get_recordmode:
        if not opts.uuid:
            print('Name or UUID is required')
            return 1
        r = client.get_recordmode(opts.uuid)
        print(r)
        return r == 'none'

    elif opts.get_externalirmode:
        if not opts.uuid:
            print('Name or UUID is required')
            return 1
        r = client.get_externalirmode(opts.uuid)
        print(r)
        return r == 'none'

    elif opts.get_irsensitivity:
        if not opts.uuid:
            print('Name or UUID is required')
            return 1
        r = client.get_irsensitivity(opts.uuid)
        print(r)
        return r == 'none'

    elif opts.get_irledmode:
        if not opts.uuid:
            print('Name or UUID is required')
            return 1
        r = client.get_irledmode(opts.uuid)
        print(r)
        return r == 'none'

    elif opts.get_picture_settings:
        settings = client.get_picture_settings(opts.uuid)
        print(','.join(['%s=%s' % (k, v) for k, v in settings.items()]))
        return 0
    elif opts.set_picture_settings:
        settings = {}
        try:
            for setting in opts.set_picture_settings.split(','):
                k, v = setting.split('=')
                settings[k] = v
        except ValueError:
            print('Invalid picture setting string format')
            return 1
        try:
            result = client.set_picture_settings(opts.uuid, settings)
        except Invalid as e:
            print('Invalid value: %s' % e)
            return 1
        for k in settings:
            if type(result[k])(settings[k]) != result[k]:
                print('Rejected: %s' % k)
        return 0
    elif opts.set_led is not None:
        camera = client.get_camera(opts.uuid)
        if not camera:
            print('No such camera')
            return 1
        if 'Micro' not in camera['model']:
            print('Only micro cameras support LED status')
            return 2
        do_led(camera, opts.set_led.lower() == 'on')
    elif opts.prune_zones:
        if not opts.uuid:
            print('Name or UUID is required')
            return 1
        client.prune_zones(opts.uuid)
    elif opts.list_zones:
        if not opts.uuid:
            print('Name or UUID is required')
            return 1
        zones = client.list_zones(opts.uuid)
        for zone in zones:
            print(zone['name'])
    elif opts.get_snapshot:
        camera = client.get_camera(opts.uuid)
        if not camera:
            print('No such camera')
            return 1
        if hasattr(sys.stdout, 'buffer'):
            # sys.stdout.buffer.write(do_snapshot(client, camera))
            sys.stdout.buffer.write(client.get_snapshot(opts.uuid))
        else:
            sys.stdout.write(do_snapshot(client, camera))
    elif opts.set_password:
        do_set_password(opts)
    elif opts.get_allalerts:
        data = client.get_all_alerts()
        for alert in data:
            pprint.pprint(alert)
    elif opts.delete_alert:
        data = client.get_all_alerts()
        for alert in data:
            if opts.timestamp is not None:
                if alert['timestamp'] == opts.timestamp:
                    alert['alertState'] = 'deleted'
                    if client.delete_alert(alert)['timestamp'] == opts.timestamp:
                        print("Alert Deleted")
                    else:
                        print("Failed to delete alert")
            if opts.alert_type is not None:
                if opts.alert_type == str(alert['alertType']):
                    alert['alertState'] = 'deleted'
                    resp = client.delete_alert(alert)
                    if resp['data'][0]['alertType'] == opts.alert_type:
                        print("Alert " + resp['data'][0]['_id'] + " Deleted")
                    else:
                        print("Failed to delete alert")
    elif opts.delete_allalerts is not None:
        data = client.get_all_alerts()
        for alert in data:
            alert['alertState'] = 'deleted'
            resp = client.delete_alert(alert)
            if resp['data'][0]['_id'] == alert['_id']:
                print("Alert " + resp['data'][0]['_id'] + " Deleted")
            else:
                print("Failed to delete alert")

        data = client.get_all_alerts()
        if len(data) <= 1:
            print("All alerts deleted")
        else:
            print(str(len(data)) + " alerts remaining following deletion")
    elif opts.test_login:
        resp = client.test_login(opts.username, opts.password)
        if resp.status == 200:
            print("login successful")
            return 0
        else:
            print("login failed status=" + str(resp.status) + " error=" + resp.reason)
            return 1
