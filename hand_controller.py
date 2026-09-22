# SPDX-FileCopyrightText: 2026 GoodWin (GodsWarior)
# SPDX-License-Identifier: MIT
#
# Этот файл является частью проекта HandDeviceController и распространяется
# под лицензией MIT. Полный текст лицензии — в файле LICENSE.

import math
from dataclasses import dataclass

import mediapipe as mp
import pyautogui


@dataclass
class ControllerSettings:
    sensitivity_x: float
    sensitivity_y: float
    move_threshold: float
    click_threshold: float
    dead_zone_ratio: float
    smoothing: int


class HandMouseController:
    def __init__(self, settings: ControllerSettings):
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.7,
            min_tracking_confidence=0.5,
        )
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles

        self.screen_width, self.screen_height = pyautogui.size()

        self.settings = settings
        self.prev_x, self.prev_y = 0, 0

        self.click_gesture_active = False
        self.prev_fist_center_y = None

    # Свойства для удобной работы из main.py
    @property
    def sensitivity_x(self) -> float:
        return self.settings.sensitivity_x

    @sensitivity_x.setter
    def sensitivity_x(self, value: float) -> None:
        self.settings.sensitivity_x = value

    @property
    def sensitivity_y(self) -> float:
        return self.settings.sensitivity_y

    @sensitivity_y.setter
    def sensitivity_y(self, value: float) -> None:
        self.settings.sensitivity_y = value

    @staticmethod
    def calculate_distance(point1, point2) -> float:
        return math.sqrt((point1.x - point2.x) ** 2 + (point1.y - point2.y) ** 2)

    def are_fingers_pinched(self, hand_landmarks, finger_ids) -> bool:
        thumb_tip = hand_landmarks.landmark[4]

        for finger_id in finger_ids:
            finger_tip = hand_landmarks.landmark[finger_id]
            distance = self.calculate_distance(thumb_tip, finger_tip)
            if distance > self.settings.click_threshold:
                return False
        return True

    def is_pinching(self, hand_landmarks, finger1_id, finger2_id) -> bool:
        return self.are_fingers_pinched(hand_landmarks, [finger1_id, finger2_id])

    def is_click_gesture(self, hand_landmarks) -> bool:
        # Если распознан кулак, клик не должен срабатывать
        if self.is_fist(hand_landmarks):
            return False
        return self.are_fingers_pinched(hand_landmarks, [8, 12])

    def is_scrolling_gesture(self, hand_landmarks) -> bool:
        return self.are_fingers_pinched(hand_landmarks, [12])

    def is_fist(self, hand_landmarks) -> bool:
        """
        Специальный жест для скролла: сомкнуты большой и безымянный пальцы.
        """
        # Безымянный палец: tip id = 16
        return self.are_fingers_pinched(hand_landmarks, [16])

    def get_fist_center_y(self, hand_landmarks, frame_shape) -> float:
        """
        Возвращает среднее Y (в пикселях) для кончиков пальцев — используется как
        вертикальная позиция кулака для управления скроллом.
        """
        h, w, _ = frame_shape
        tip_ids = [4, 8, 12, 16, 20]
        ys = []
        for tip_id in tip_ids:
            tip = hand_landmarks.landmark[tip_id]
            ys.append(tip.y * h)
        return sum(ys) / len(ys)

    def get_index_finger_position(self, hand_landmarks, frame_shape):
        h, w, _ = frame_shape
        index_tip = hand_landmarks.landmark[8]

        target_x = int(index_tip.x * w)
        target_y = int(index_tip.y * h)

        if self.prev_x == 0 and self.prev_y == 0:
            self.prev_x, self.prev_y = target_x, target_y

        smooth_x = self.prev_x + (target_x - self.prev_x) / self.settings.smoothing
        smooth_y = self.prev_y + (target_y - self.prev_y) / self.settings.smoothing

        self.prev_x, self.prev_y = smooth_x, smooth_y

        return smooth_x, smooth_y

    def map_to_screen_with_sensitivity(self, x, y, frame_shape):
        h, w, _ = frame_shape

        norm_x = (x / w) - 0.5
        norm_y = (y / h) - 0.5

        norm_x *= self.settings.sensitivity_x
        norm_y *= self.settings.sensitivity_y

        norm_x = max(-0.5, min(0.5, norm_x))
        norm_y = max(-0.5, min(0.5, norm_y))

        screen_x = (norm_x + 0.5) * self.screen_width
        screen_y = (norm_y + 0.5) * self.screen_height

        center_x = self.screen_width / 2
        center_y = self.screen_height / 2
        dead_zone_x = self.screen_width * self.settings.dead_zone_ratio
        dead_zone_y = self.screen_height * self.settings.dead_zone_ratio

        if abs(screen_x - center_x) < dead_zone_x:
            factor = abs(screen_x - center_x) / dead_zone_x
            screen_x = center_x + (screen_x - center_x) * factor

        if abs(screen_y - center_y) < dead_zone_y:
            factor = abs(screen_y - center_y) / dead_zone_y
            screen_y = center_y + (screen_y - center_y) * factor

        screen_x = max(0, min(screen_x, self.screen_width))
        screen_y = max(0, min(screen_y, self.screen_height))

        return int(screen_x), int(screen_y)

    def close(self):
        self.hands.close()


