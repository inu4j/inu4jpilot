#!/usr/bin/env python3
import os
import json
from atomicwrites import atomic_write
from common.colors import COLORS
from common.travis_checker import BASEDIR
from selfdrive.hardware import TICI
try:
  from common.realtime import sec_since_boot
except ImportError:
  import time
  sec_since_boot = time.time

warning = lambda msg: print('{}opParams WARNING: {}{}'.format(COLORS.WARNING, msg, COLORS.ENDC))
error = lambda msg: print('{}opParams ERROR: {}{}'.format(COLORS.FAIL, msg, COLORS.ENDC))

NUMBER = [float, int]  # value types
NONE_OR_NUMBER = [type(None), float, int]

BASEDIR = os.path.dirname(BASEDIR)
PARAMS_DIR = os.path.join(BASEDIR, 'community', 'params')
IMPORTED_PATH = os.path.join(PARAMS_DIR, '.imported')
OLD_PARAMS_FILE = os.path.join(BASEDIR, 'op_params.json')


class Param:
  def __init__(self, default, allowed_types=[], description=None, *, static=False, live=False, hidden=False):  # pylint: disable=dangerous-default-value
    self.default_value = default  # value first saved and returned if actual value isn't a valid type
    if not isinstance(allowed_types, list):
      allowed_types = [allowed_types]
    self.allowed_types = allowed_types  # allowed python value types for opEdit
    self.description = description  # description to be shown in opEdit
    self.hidden = hidden  # hide this param to user in opEdit
    self.live = live  # show under the live menu in opEdit
    self.static = static  # use cached value, never reads to update
    self._create_attrs()

  def is_valid(self, value):
    if not self.has_allowed_types:  # always valid if no allowed types, otherwise checks to make sure
      return True
    return type(value) in self.allowed_types

  def _create_attrs(self):  # Create attributes and check Param is valid
    self.has_allowed_types = isinstance(self.allowed_types, list) and len(self.allowed_types) > 0
    self.has_description = self.description is not None
    self.is_list = list in self.allowed_types
    self.read_frequency = None if self.static else (1 if self.live else 10)  # how often to read param file (sec)
    self.last_read = -1
    if self.has_allowed_types:
      assert type(self.default_value) in self.allowed_types, 'Default value type must be in specified allowed_types!'
    if self.is_list:
      self.allowed_types.remove(list)


def _read_param(key):  # Returns None, False if a json error occurs
  try:
    with open(os.path.join(PARAMS_DIR, key), 'r') as f:
      value = json.loads(f.read())
    return value, True
  except json.decoder.JSONDecodeError:
    return None, False


def _write_param(key, value):
  param_path = os.path.join(PARAMS_DIR, key)
  with atomic_write(param_path, overwrite=True) as f:
    f.write(json.dumps(value))


def _import_params():
  if os.path.exists(OLD_PARAMS_FILE) and not os.path.exists(IMPORTED_PATH):  # if opParams needs to import from old params file
    try:
      with open(OLD_PARAMS_FILE, 'r') as f:
        old_params = json.loads(f.read())
      for key in old_params:
        _write_param(key, old_params[key])
      open(IMPORTED_PATH, 'w').close()
    except:  # pylint: disable=bare-except
      pass

# Korean by inu4j
class opParams:
  def __init__(self): 
    """
      포크의 opParams에 고유한 매개변수를 추가하려면 self.fork_params에 새 항목을 추가하고 최소 기본값으로 새 Param 클래스를 인스턴스화합니다.
      allowed_types 및 description args는 필수는 아니지만 사용자가 opEdit를 사용하여 매개변수를 안전하게 편집할 수 있도록 적극 권장합니다.
        - 사용자가 opEdit를 사용하여 매개변수 값을 변경할 때 설명 값이 표시됩니다.
        - allowed_types 인수는 사용자가 의도하지 않은 동작으로 openpilot을 충돌시킬 수 없도록 opEdit로 입력할 수 있는 값의 종류를 제한하는 데 사용됩니다.
          (예를 들어 부울이 있는 숫자가 되도록 매개변수를 설정하거나 그 반대의 경우)
          매개변수를 `.get`할 때 부동 소수점 또는 정수의 범위를 제한하는 것이 여전히 권장됩니다.
          None 값이 허용되면 opEdit가 `isinstance()`를 사용하여 arg의 값에 대해 유형을 확인하므로 None 대신 `type(None)`을 사용합니다.
        - 매개변수가 1초 이내에 업데이트되도록 하려면 live=True를 지정하십시오. 매개변수가 한 번만 읽히도록 설계된 경우 static=True를 지정하십시오.
          둘 다 지정하지 않으면 지속적으로 .get()인 경우 매개변수가 10초마다 업데이트됩니다.
          매개변수가 정적이지 않은 경우 실시간 업데이트를 사용하기 위해 읽고 있는 파일의 업데이트 함수에서 .get() 함수를 호출합니다.
      
      다음은 좋은 fork_param 항목의 예입니다.
      self.fork_params = {'camera_offset': Param(0.06, allowed_types=NUMBER), live=True} # NUMBER는 부동 소수점과 정수를 모두 허용합니다.
    """

    self.fork_params = {
      # 'camera_offset': Param(-0.04 if TICI else 0.06, NUMBER, 'Your camera offset to use in lane_planner.py, live=True),
      'global_df_mod': Param(1.0, NUMBER, '동적 추적에서 사용하는 현재 거리의 승수입니다. 범위는 0.85에서 2.5로 제한됩니다.\n'
                                          '값이 작을수록 가까워지고 클수록 멀어집니다.\n'
                                          '이것은 활성 상태인 프로필로 곱해집니다. 비활성화하려면 1로 설정하십시오.', live=True),
      'min_TR': Param(0.9, NUMBER, '허용되는 최소 추종 거리(초)입니다. 기본값은 0.9초입니다.\n'
                                   '범위는 0.85에서 2.7로 제한됩니다.', live=True),
      'alca_no_nudge_speed': Param(90., NUMBER, '이 속도(mph) 이상에서는 차선 변경이 즉시 시작됩니다. 작동은 저장값 아래에 있습니다'),
      'steer_ratio': Param(None, NONE_OR_NUMBER, '(Can be: None, or a float) None을 입력하면 openpilot은 학습된 sR을 사용합니다..\n'
                                                 'float/int를 사용하는 경우 openpilot은 대신 해당 핸들링 조정 비율을 사용합니다.', live=True),
      'upload_onroad': Param(True, bool, '기본적으로 openpilot은 운전하는 동안 작은 qlog를 업로드합니다. 오프로드가 될 때까지 기다리려면 False로 설정하십시오.', static=True),
      'update_behavior': Param('alert', str, 'Can be: (\'off\', \'alert\', \'auto\') without quotes\n'
                                             'off will never update, alert shows an alert on-screen\n'
                                             'auto will reboot the device when an update is seen', static=True),
      'dynamic_gas': Param(False, bool, 'Whether to use dynamic gas if your car is supported'),
      'hide_auto_df_alerts': Param(False, bool, 'DF모델이 선택한 프로필을 보여주는 경고를 숨깁니다.'),
      'df_button_alerts': Param('audible', str, 'Can be: (\'off\', \'silent\', \'audible\')\n'
                                                'dynamic following profile을 변경할 때 알림을 받는 방법 '),
      # 'log_auto_df': Param(False, bool, 'Logs dynamic follow data for auto-df', static=True),
      # 'dynamic_camera_offset': Param(False, bool, 'Whether to automatically keep away from oncoming traffic.\n'
      #                                             'Works from 35 to ~60 mph (requires radar)'),
      # 'dynamic_camera_offset_time': Param(3.5, NUMBER, 'How long to keep away from oncoming traffic in seconds after losing lead'),
      'disable_charging': Param(30, NUMBER, 'How many hours until charging is disabled while idle', static=True),
      'hide_model_long': Param(False, bool, '화면에서 Model Long 버튼을 숨기려면 이 옵션을 활성화합니다.', static=True),
      'use_steering_model': Param(False, bool, 'TSSP Corolla에서 훈련된 실험적 ML 기반 측면 컨트롤러를 사용하려면 이 옵션을 활성화합니다.\n'
                                               '이것은 다른 모든 조정 매개변수를 무시합니다.\n'
                                               '경고: 모델은 언제든지 예기치 않게 작동할 수 있으므로 항상 주의하십시오.', static=True),
      'rav4TSS2_use_indi': Param(False, bool, 'TSS2 RAV4에서 횡조정 대해 INDI를 사용하려면 이 옵션을 활성화하세요.', static=True),
      'standstill_hack': Param(False, bool, '일부 자동차는 정지 및 이동을 지원합니다. 이 기능을 활성화하기만 하면 됩니다.', static=True),
      'toyota_distance_btn': Param(False, bool, '다이내믹 팔로우 프로파일을 제어하기 위해 스티어링 휠 거리 버튼을 사용하려면 True로 설정하십시오..\n'
                                                '2020년 9월 펌웨어 이상이 설치된 sDSU가 있는 TSS2 차량 및 TSS1 차량에서 작동.', static=True),

      'dynamic_follow': Param('stock', str, static=True, hidden=True),
      'lane_speed_alerts': Param('silent', str, static=True, hidden=True),
    }

    self._to_delete = ['use_lqr', 'disengage_on_gas', 'corollaTSS2_use_indi', 'prius_use_pid']  # a list of unused params you want to delete from users' params file
    self._to_reset = []  # a list of params you want reset to their default values
    self._run_init()  # restores, reads, and updates params

  def _run_init(self):  # does first time initializing of default params
    # Two required parameters for opEdit
    self.fork_params['username'] = Param(None, [type(None), str, bool], 'Your identifier provided with any crash logs sent to Sentry.\nHelps the developer reach out to you if anything goes wrong')
    self.fork_params['op_edit_live_mode'] = Param(False, bool, 'This parameter controls which mode opEdit starts in', hidden=True)

    self.params = self._load_params(can_import=True)
    self._add_default_params()  # adds missing params and resets values with invalid types to self.params
    self._delete_and_reset()  # removes old params

  def get(self, key=None, *, force_update=False):  # key=None returns dict of all params
    if key is None:
      return self._get_all_params(to_update=force_update)
    self._check_key_exists(key, 'get')
    param_info = self.fork_params[key]
    rate = param_info.read_frequency  # will be None if param is static, so check below

    if (not param_info.static and sec_since_boot() - self.fork_params[key].last_read >= rate) or force_update:
      value, success = _read_param(key)
      self.fork_params[key].last_read = sec_since_boot()
      if not success:  # in case of read error, use default and overwrite param
        value = param_info.default_value
        _write_param(key, value)
      self.params[key] = value

    if param_info.is_valid(value := self.params[key]):
      return value  # all good, returning user's value
    print(warning('User\'s value type is not valid! Returning default'))  # somehow... it should always be valid
    return param_info.default_value  # return default value because user's value of key is not in allowed_types to avoid crashing openpilot

  def put(self, key, value):
    self._check_key_exists(key, 'put')
    if not self.fork_params[key].is_valid(value):
      raise Exception('opParams: Tried to put a value of invalid type!')
    self.params.update({key: value})
    _write_param(key, value)

  def _load_params(self, can_import=False):
    if not os.path.exists(PARAMS_DIR):
      os.makedirs(PARAMS_DIR)
      if can_import:
        _import_params()  # just imports old params. below we read them in

    params = {}
    for key in os.listdir(PARAMS_DIR):  # PARAMS_DIR is guaranteed to exist
      if key.startswith('.') or key not in self.fork_params:
        continue
      value, success = _read_param(key)
      if not success:
        value = self.fork_params[key].default_value
        _write_param(key, value)
      params[key] = value
    return params

  def _get_all_params(self, to_update=False):
    if to_update:
      self.params = self._load_params()
    return {k: self.params[k] for k, p in self.fork_params.items() if k in self.params and not p.hidden}

  def _check_key_exists(self, key, met):
    if key not in self.fork_params:
      raise Exception('opParams: Tried to {} an unknown parameter! Key not in fork_params: {}'.format(met, key))

  def _add_default_params(self):
    for key, param in self.fork_params.items():
      if key not in self.params:
        self.params[key] = param.default_value
        _write_param(key, self.params[key])
      elif not param.is_valid(self.params[key]):
        print(warning('Value type of user\'s {} param not in allowed types, replacing with default!'.format(key)))
        self.params[key] = param.default_value
        _write_param(key, self.params[key])

  def _delete_and_reset(self):
    for key in list(self.params):
      if key in self._to_delete:
        del self.params[key]
        os.remove(os.path.join(PARAMS_DIR, key))
      elif key in self._to_reset and key in self.fork_params:
        self.params[key] = self.fork_params[key].default_value
        _write_param(key, self.params[key])
