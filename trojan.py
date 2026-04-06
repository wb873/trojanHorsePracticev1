#!/usr/bin/env python3
"""
teacher_messaging_guess.py

Number guessing game (main thread) + background "teacher message" thread.
Teacher connects with: nc localhost 9999
"""

import threading
import socket
import random
import sys
import time

# Attempt to import readline for nicer prompt preservation (Unix)
try:
    import readline
    HAVE_READLINE = True
except Exception:
    HAVE_READLINE = False

HOST = "0.0.0.0"
PORT = 9999

# A simple synchronized print so messages don't interleave badly
print_lock = threading.Lock()

def safe_print(*args, **kwargs):
    with print_lock:
        print(*args, **kwargs)
        sys.stdout.flush()

def display_teacher_message(msg):
    """
    Print teacher message without destroying the student's current input line,
    using readline if available.
    """
    with print_lock:
        if HAVE_READLINE:
            # Save current buffer and cursor position
            try:
                cur = readline.get_line_buffer()
                # Move to new line and print teacher message
                sys.stdout.write("\n")
                sys.stdout.write(f"[TEACHER] {msg}\n")
                # Reprint the prompt and the partially typed buffer
                # We can't know the original prompt string, so we reprint a standard prompt
                # Then write the user's buffer back and redisplay
                sys.stdout.write(f"> {cur}")
                sys.stdout.flush()
                readline.redisplay()
            except Exception:
                # fallback
                sys.stdout.write(f"\n[TEACHER] {msg}\n> ")
                sys.stdout.flush()
        else:
            # simple fallback: newline then message then reprint generic prompt
            sys.stdout.write(f"\n[TEACHER] {msg}\n> ")
            sys.stdout.flush()

def teacher_server(stop_event):
    """
    Simple TCP server that accepts one line messages from connected clients.
    Each received line is shown to the student's CLI as a teacher message.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((HOST, PORT))
        except OSError as e:
            safe_print(f"ERROR: Could not bind to {HOST}:{PORT} — {e}")
            safe_print("Teacher messaging disabled.")
            return
        s.listen(1)
        safe_print(f"(Teacher message server listening on {HOST}:{PORT})")
        # Accept connections until stop_event is set
        s.settimeout(1.0)
        while not stop_event.is_set():
            try:
                conn, addr = s.accept()
            except socket.timeout:
                continue
            with conn:
                safe_print(f"\n(Teacher connected from {addr})")
                # Receive data line by line
                # We will read bytes and split on newline to support partial sends
                buffer = b""
                conn.settimeout(0.5)
                while not stop_event.is_set():
                    try:
                        data = conn.recv(1024)
                        if not data:
                            break
                        buffer += data
                        while b"\n" in buffer:
                            line, buffer = buffer.split(b"\n", 1)
                            line = line.decode('utf-8', 'replace').strip()
                            if line:
                                display_teacher_message(line)
                                # special command: teacher can type "__END_GAME__" to end the game
                                if line.strip() == "__END_GAME__":
                                    display_teacher_message("(teacher requested end of game)")
                                    stop_event.set()
                                    break
                    except socket.timeout:
                        continue
                    except Exception as e:
                        safe_print(f"(teacher connection error: {e})")
                        break
                safe_print("(Teacher disconnected)")

def number_guessing_game():
    """
    Main interactive guessing game loop.
    """
    secret = random.randint(1, 100)
    attempts = 0
    safe_print("Welcome to the Number Guessing Game!")
    safe_print("I'm thinking of a number between 1 and 100.")
    safe_print("Type 'quit' to give up. Try to guess!")
    while True:
        try:
            # We use a consistent prompt so the teacher message display can reprint it.
            guess_str = input("> ").strip()
        except EOFError:
            safe_print("\nInput closed. Exiting game.")
            break
        except KeyboardInterrupt:
            safe_print("\nInterrupted. Exiting game.")
            break

        if not guess_str:
            continue
        if guess_str.lower() in ("quit", "exit"):
            safe_print("You gave up. The number was: " + str(secret))
            break

        attempts += 1
        # validate
        try:
            guess = int(guess_str)
        except ValueError:
            safe_print("Please enter an integer between 1 and 100.")
            continue

        if guess < secret:
            safe_print("Too low.")
        elif guess > secret:
            safe_print("Too high.")
        else:
            safe_print(f"Correct! The number was {secret}. Attempts: {attempts}")
            break

def main():
    stop_event = threading.Event()
    server_thread = threading.Thread(target=teacher_server, args=(stop_event,), daemon=True)
    server_thread.start()

    try:
        number_guessing_game()
    finally:
        # signal the server to stop and wait a little
        stop_event.set()
        server_thread.join(timeout=1.0)
        safe_print("Game exited. Teacher server stopped.")

if __name__ == "__main__":
    main()

