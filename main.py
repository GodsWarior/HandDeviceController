# SPDX-FileCopyrightText: 2026 GoodWin (GodsWarior)
# SPDX-License-Identifier: MIT
#
# Этот файл является частью проекта HandDeviceController и распространяется
# под лицензией MIT. Полный текст лицензии — в файле LICENSE.

import time
import platform
import ctypes

import cv2
import pyautogui

from config_loader import load_config
from hand_controller import HandMouseController, ControllerSettings


# Настройки для более плавного управления
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0


def check_window_state(window_name):
    """Проверяет, свёрнуто ли окно"""
    try:
        # Получаем состояние окна
        state = cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE)
        return state < 1
    except:
        return False


def set_high_priority():
    """
    Повышает приоритет процесса под Windows, чтобы уменьшить проседания FPS
    при свёрнутом/фоновом окне.
    """
    if platform.system() != "Windows":
        return

    try:
        PROCESS_SET_INFORMATION = 0x0200
        HIGH_PRIORITY_CLASS = 0x00000080

        handle = ctypes.windll.kernel32.GetCurrentProcess()
        ctypes.windll.kernel32.SetPriorityClass(handle, HIGH_PRIORITY_CLASS)
        print("✅ Приоритет процесса повышен до HIGH_PRIORITY_CLASS")
    except Exception as e:
        print(f"⚠️ Не удалось повысить приоритет процесса: {e}")


def main():
    # Попытаться повысить приоритет, чтобы фон не резал FPS
    set_high_priority()

    config = load_config()

    controller_settings = ControllerSettings(
        sensitivity_x=config.sensitivity.x,
        sensitivity_y=config.sensitivity.y,
        move_threshold=config.thresholds.move,
        click_threshold=config.thresholds.click,
        dead_zone_ratio=config.dead_zone_ratio,
        smoothing=config.smoothing,
    )
    controller = HandMouseController(controller_settings)

    cap = cv2.VideoCapture(config.camera.device_index)

    # Оптимизация захвата видео
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.camera.frame_width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.camera.frame_height)
    cap.set(cv2.CAP_PROP_FPS, config.camera.fps)

    if not cap.isOpened():
        print("Ошибка: Не удалось открыть веб-камеру")
        return

    print("=== УПРАВЛЕНИЕ КУРСОРОМ ЖЕСТАМИ ===")
    print("🖐️ Режимы работы:")
    print("  • Сомкните указательный и большой пальцы - перемещение курсора")
    print("  • Сомкните средний и большой пальцы - скроллинг")
    print("  • Сомкните большой, указательный и средний пальцы - ЛКМ (клик)")
    print("\n⚙️ Текущие настройки:")
    print(f"  • Чувствительность X: {controller.sensitivity_x}")
    print(f"  • Чувствительность Y: {controller.sensitivity_y}")
    print("  • Разрешение камеры: 640x480 (оптимизировано)")
    print("\n⌨️ Управление:")
    print("  • Q или ESC - выход")
    print("  • +/- - увеличить/уменьшить чувствительность")
    print("  • R - сбросить настройки")
    print("  • M - вкл/выкл оптимизацию при свёрнутом окне")
    print("=" * 40)

    prev_time = 0
    last_click_time = 0
    click_cooldown = config.click_cooldown_seconds

    # Настройки оптимизации
    # При свёрнутом окне обработка жестов продолжается в полном объёме.
    # Оптимизация управляет только выводом окна.
    minimize_optimization = config.optimization.minimize_optimization_default

    # Фоновый режим: окно "прячется" за пределы экрана и уменьшается до 1x1.
    background_mode = config.optimization.background_mode_default

    window_name = 'Hand Mouse Controller'
    cv2.namedWindow(window_name)

    # Текущий активный режим жеста: None / "move" / "scroll_fingers" / "scroll_ring"
    current_mode = None

    while cap.isOpened():
        # Проверяем, свёрнуто ли окно (только для управления выводом изображения),
        # но в фоновом режиме мы сознательно НЕ сворачиваем окно, а прячем его за экран.
        window_minimized = False
        if not background_mode:
            try:
                window_minimized = check_window_state(window_name)
            except Exception:
                window_minimized = False

        success, frame = cap.read()
        if not success:
            print("Не удалось получить кадр с веб-камеры")
            break

        frame = cv2.flip(frame, 1)
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = controller.hands.process(frame_rgb)

        current_time = time.time()
        fps = 1 / (current_time - prev_time) if prev_time > 0 else 0
        prev_time = current_time

        h, w, _ = frame.shape

        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                controller.mp_drawing.draw_landmarks(
                    frame,
                    hand_landmarks,
                    controller.mp_hands.HAND_CONNECTIONS,
                    controller.mp_drawing_styles.get_default_hand_landmarks_style(),
                    controller.mp_drawing_styles.get_default_hand_connections_style()
                )

                index_x, index_y = controller.get_index_finger_position(hand_landmarks, frame.shape)
                index_pixel = (int(index_x), int(index_y))

                cv2.circle(frame, index_pixel, 10, (0, 255, 0), -1)

                pinching = controller.is_pinching(hand_landmarks, 4, 8)
                scrolling = controller.is_scrolling_gesture(hand_landmarks)
                click_gesture = controller.is_click_gesture(hand_landmarks)
                fist = controller.is_fist(hand_landmarks)

                # Если режим ещё не выбран и есть какой‑то жест — фиксируем режим до его завершения
                if current_mode is None:
                    if fist:
                        current_mode = "scroll_ring"
                    elif pinching:
                        current_mode = "move"
                    elif scrolling:
                        current_mode = "scroll_fingers"

                # Клик обрабатываем отдельно: его можно делать и в режиме перемещения курсора.
                # При этом клик не срабатывает во время режимов скролла.
                if click_gesture and current_mode in (None, "move"):
                    if not controller.click_gesture_active and current_time - last_click_time > click_cooldown:
                        try:
                            pyautogui.click()
                        except pyautogui.FailSafeException:
                            pass
                        last_click_time = current_time
                        print("🖱️ Клик!")
                        controller.click_gesture_active = True

                        cv2.putText(frame, "КЛИК!", (w // 2 - 50, h // 2),
                                    cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 3)
                else:
                    controller.click_gesture_active = False

                # Обработка по текущему режиму.
                # Другие жесты (кроме клика в режиме move) игнорируются,
                # пока режим не будет сброшен (пальцы разомкнуты).
                if current_mode == "scroll_ring":
                    cv2.putText(frame, "РЕЖИМ КЛИКА", (10, 60),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

                    thumb_tip = hand_landmarks.landmark[4]
                    thumb_pixel = (int(thumb_tip.x * w), int(thumb_tip.y * h))
                    index_tip = hand_landmarks.landmark[8]
                    index_pixel = (int(index_tip.x * w), int(index_tip.y * h))
                    middle_tip = hand_landmarks.landmark[12]
                    middle_pixel = (int(middle_tip.x * w), int(middle_tip.y * h))

                    cv2.line(frame, thumb_pixel, index_pixel, (255, 255, 255), 3)
                    cv2.line(frame, thumb_pixel, middle_pixel, (255, 255, 255), 3)
                    cv2.line(frame, index_pixel, middle_pixel, (255, 255, 255), 3)

                    if fist:
                        fist_center_y = controller.get_fist_center_y(hand_landmarks, frame.shape)

                        if controller.prev_fist_center_y is not None:
                            delta = controller.prev_fist_center_y - fist_center_y
                            scroll_amount = int(delta / 0.5)
                            if scroll_amount != 0:
                                # Инвертируем направление: движение руки вверх = скролл вниз и наоборот
                                try:
                                    pyautogui.scroll(-scroll_amount * 3)
                                except pyautogui.FailSafeException:
                                    pass

                            cv2.putText(frame, f"delta={delta:.1f} scroll={scroll_amount}",
                                        (10, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                                        (0, 200, 255), 1)

                        controller.prev_fist_center_y = fist_center_y

                        cv2.putText(frame, "СКРОЛЛ (большой+безымянный)", (10, 60),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 255), 2)
                    else:
                        controller.prev_fist_center_y = None
                        current_mode = None

                elif current_mode == "move":
                    if pinching:
                        screen_x, screen_y = controller.map_to_screen_with_sensitivity(
                            index_x, index_y, frame.shape
                        )
                        try:
                            pyautogui.moveTo(screen_x, screen_y)
                        except pyautogui.FailSafeException:
                            # Игнорируем срабатывание fail-safe, чтобы не падало приложение
                            pass

                        cv2.putText(frame, f"Курсор: X={screen_x}, Y={screen_y}", (10, 90),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

                        cv2.putText(frame, "ПЕРЕМЕЩЕНИЕ КУРСОРА", (10, 60),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

                        thumb_tip = hand_landmarks.landmark[4]
                        thumb_pixel = (int(thumb_tip.x * w), int(thumb_tip.y * h))
                        cv2.line(frame, index_pixel, thumb_pixel, (0, 255, 0), 3)
                    else:
                        current_mode = None

                elif current_mode == "scroll_fingers":
                    if scrolling:
                        screen_x, screen_y = controller.map_to_screen_with_sensitivity(
                            index_x, index_y, frame.shape
                        )

                        if hasattr(controller, 'prev_scroll_y'):
                            scroll_amount = int((controller.prev_scroll_y - screen_y) / 3)
                            if abs(scroll_amount) > 1:
                                # Инвертируем направление скролла
                                try:
                                    pyautogui.scroll(-scroll_amount)
                                except pyautogui.FailSafeException:
                                    pass

                        controller.prev_scroll_y = screen_y

                        cv2.putText(frame, "СКРОЛЛИНГ (пальцы)", (10, 60),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 165, 0), 2)

                        thumb_tip = hand_landmarks.landmark[4]
                        thumb_pixel = (int(thumb_tip.x * w), int(thumb_tip.y * h))
                        middle_tip = hand_landmarks.landmark[12]
                        middle_pixel = (int(middle_tip.x * w), int(middle_tip.y * h))
                        cv2.line(frame, thumb_pixel, middle_pixel, (255, 165, 0), 3)
                    else:
                        if hasattr(controller, "prev_scroll_y"):
                            delattr(controller, "prev_scroll_y")
                        current_mode = None

                else:
                    # Нет активного режима — сбрасываем вспомогательные значения и рисуем подсказки
                    if hasattr(controller, "prev_scroll_y"):
                        delattr(controller, "prev_scroll_y")
                    controller.prev_fist_center_y = None
                    colors = [(255, 0, 0), (0, 255, 0), (255, 165, 0), (255, 255, 0), (255, 0, 255)]
                    for i, tip_id in enumerate([4, 8, 12, 16, 20]):
                        tip = hand_landmarks.landmark[tip_id]
                        tip_pixel = (int(tip.x * w), int(tip.y * h))
                        cv2.circle(frame, tip_pixel, 8, colors[i % len(colors)], -1)

                    cv2.putText(frame, "ОЖИДАНИЕ ЖЕСТА", (10, 60),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (100, 100, 100), 2)

        # Отображаем информацию и окно только если оно не свёрнуто
        # или оптимизация отключена. В противном случае работаем "вслепую"
        # без перерисовки окна и без waitKey, чтобы не терять FPS.
        if not window_minimized or not minimize_optimization:
            cv2.putText(frame, f"FPS: {int(fps)}", (w - 100, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

            cv2.putText(frame, f"Чувст.X: {controller.sensitivity_x:.1f} Чувст.Y: {controller.sensitivity_y:.1f}",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

            # Подсказка по жестам
            gestures_y = h - 150
            cv2.putText(frame, "Жесты:", (10, gestures_y),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
            cv2.putText(frame, "👆+👍 = движение", (10, gestures_y + 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
            cv2.putText(frame, "👍+👌 = скролл", (10, gestures_y + 35),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
            cv2.putText(frame, "👆+👍+👌 = клик", (10, gestures_y + 50),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)

            # Статус оптимизации и фонового режима
            opt_status = "ВКЛ" if minimize_optimization else "ВЫКЛ"
            bg_status = "ВКЛ" if background_mode else "ВЫКЛ"
            cv2.putText(frame, f"Оптимизация: {opt_status} (M)  Фон: {bg_status} (B)", (10, gestures_y + 70),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                        (100, 255, 100) if minimize_optimization else (255, 100, 100), 1)

            cv2.putText(frame, "+/- чувств. | R сброс | Q: выход | B: фон", (10, h - 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

            cv2.imshow(window_name, frame)
            key = cv2.waitKey(1) & 0xFF
        else:
            # Окно свёрнуто и оптимизация включена:
            # не вызываем imshow и waitKey, чтобы избежать просадки FPS.
            key = -1
            time.sleep(0.001)
        if key == ord('q') or key == 27:
            break
        elif key == ord('+') or key == ord('='):
            controller.sensitivity_x += 0.1
            controller.sensitivity_y += 0.1
            print(f"✅ Чувствительность увеличена: X={controller.sensitivity_x:.1f}, Y={controller.sensitivity_y:.1f}")
        elif key == ord('-') or key == ord('_'):
            controller.sensitivity_x = max(0.5, controller.sensitivity_x - 0.1)
            controller.sensitivity_y = max(0.5, controller.sensitivity_y - 0.1)
            print(f"✅ Чувствительность уменьшена: X={controller.sensitivity_x:.1f}, Y={controller.sensitivity_y:.1f}")
        elif key == ord('r'):
            controller.sensitivity_x = 1.8
            controller.sensitivity_y = 1.5
            print("✅ Настройки сброшены до默认ных")
        elif key == ord('m'):
            minimize_optimization = not minimize_optimization
            print(f"✅ Оптимизация при свёрнутом окне: {'ВКЛ' if minimize_optimization else 'ВЫКЛ'}")
        elif key == ord('b'):
            background_mode = not background_mode
            if background_mode:
                # Прячем окно за пределы экрана и уменьшаем его до минимума,
                # чтобы его не нужно было сворачивать (Windows не будет его "наказывать" за сворачивание).
                cv2.resizeWindow(window_name, 1, 1)
                cv2.moveWindow(window_name, -10000, -10000)
                print("✅ Фоновый режим ВКЛ: окно скрыто, но не свёрнуто (лучший FPS в фоне)")
            else:
                # Возвращаем окно в нормальный вид
                cv2.resizeWindow(window_name, 640, 480)
                cv2.moveWindow(window_name, 100, 100)
                print("✅ Фоновый режим ВЫКЛ")

    cap.release()
    cv2.destroyAllWindows()
    controller.hands.close()


if __name__ == "__main__":
    main()