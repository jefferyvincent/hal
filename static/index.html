<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta
      name="viewport"
      content="width=device-width, initial-scale=1.0, viewport-fit=cover"
    />
    <title>HAL 9000</title>
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link
      href="https://fonts.googleapis.com/css2?family=Michroma&family=Share+Tech+Mono&display=swap"
      rel="stylesheet"
    />
    <style>
      :root {
        --red: #ff1a1a;
        --red-deep: #8a0000;
        --red-glow: #ff3838;
        --amber: #ffb300;
        --amber-bright: #ffd44a;
        --bg: #050507;
        --text-dim: #6a6a72;
        --text: #c8c8d0;
        --grid: rgba(255, 30, 30, 0.04);
      }

      * {
        box-sizing: border-box;
        margin: 0;
        padding: 0;
      }

      html,
      body {
        height: 100%;
        background: var(--bg);
        color: var(--text);
        font-family: "Share Tech Mono", "Courier New", monospace;
        overflow: hidden;
        user-select: none;
      }

      /* CRT scanlines */
      body::before {
        content: "";
        position: fixed;
        inset: 0;
        background-image: linear-gradient(
          to bottom,
          transparent 0%,
          rgba(255, 255, 255, 0.025) 50%,
          transparent 100%
        );
        background-size: 100% 4px;
        pointer-events: none;
        z-index: 100;
        mix-blend-mode: overlay;
      }

      /* Vignette */
      body::after {
        content: "";
        position: fixed;
        inset: 0;
        background: radial-gradient(
          ellipse at center,
          transparent 30%,
          rgba(0, 0, 0, 0.85) 100%
        );
        pointer-events: none;
        z-index: 99;
      }

      /* Faint grid */
      .grid {
        position: fixed;
        inset: 0;
        background-image:
          linear-gradient(var(--grid) 1px, transparent 1px),
          linear-gradient(90deg, var(--grid) 1px, transparent 1px);
        background-size: 60px 60px;
        z-index: 1;
        opacity: 0.5;
      }

      /* Top HUD */
      .hud,
      .footer {
        position: fixed;
        left: 0;
        right: 0;
        padding: 20px 32px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-size: 10px;
        letter-spacing: 4px;
        color: var(--text-dim);
        z-index: 10;
        text-transform: uppercase;
      }
      .hud {
        top: 0;
      }
      .footer {
        bottom: 0;
      }

      .hud-row {
        display: flex;
        gap: 24px;
      }
      .hud-item {
        display: flex;
        flex-direction: column;
        gap: 3px;
      }
      .hud-item .label {
        color: rgba(255, 30, 30, 0.5);
        font-size: 9px;
      }
      .hud-item .value {
        color: var(--text);
      }
      .hud-action {
        background: rgba(255, 30, 30, 0.06);
        border: 1px solid rgba(255, 30, 30, 0.35);
        padding: 5px 12px;
        font: inherit;
        color: inherit;
        text-align: left;
        cursor: pointer;
        letter-spacing: 4px;
        text-transform: uppercase;
        display: flex;
        flex-direction: column;
        gap: 3px;
        transition: background 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
      }
      .hud-action .label {
        color: var(--red);
        font-size: 9px;
      }
      .hud-action .value {
        color: #fff;
        font-weight: bold;
      }
      .hud-action:hover {
        background: rgba(255, 30, 30, 0.18);
        border-color: var(--red);
        box-shadow: 0 0 14px rgba(255, 30, 30, 0.4);
      }
      .hud-action:hover .value {
        color: var(--red-glow);
        text-shadow: 0 0 8px rgba(255, 30, 30, 0.6);
      }

      /* Conversations panel (left side) */
      .conversations {
        position: fixed;
        top: 70px;
        left: 20px;
        width: 320px;
        max-height: 50vh;
        flex-direction: column;
        background: rgba(8, 8, 11, 0.95);
        border: 1px solid var(--red);
        z-index: 500;
        backdrop-filter: blur(6px);
        font-family: "Share Tech Mono", monospace;
        box-shadow: 0 0 30px rgba(255, 30, 30, 0.4);
        display: none;
      }
      .conversations.open {
        display: flex;
      }
      .conv-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 9px 12px;
        border-bottom: 1px solid rgba(255, 30, 30, 0.2);
        font-size: 9px;
        letter-spacing: 4px;
        color: var(--red);
        text-transform: uppercase;
        background: rgba(255, 30, 30, 0.04);
      }
      .conv-new {
        background: none;
        border: 1px solid rgba(255, 30, 30, 0.4);
        color: var(--red);
        font-family: inherit;
        font-size: 9px;
        letter-spacing: 2px;
        text-transform: uppercase;
        cursor: pointer;
        padding: 3px 8px;
      }
      .conv-new:hover {
        background: rgba(255, 30, 30, 0.15);
        color: #fff;
      }
      .conv-list {
        overflow-y: auto;
        overscroll-behavior: contain;
        padding: 4px 0;
        scrollbar-width: auto;
        scrollbar-color: rgba(255, 30, 30, 0.55) rgba(255, 30, 30, 0.08);
      }
      .conv-list::-webkit-scrollbar {
        width: 12px;
      }
      .conv-list::-webkit-scrollbar-track {
        background: rgba(255, 30, 30, 0.06);
      }
      .conv-list::-webkit-scrollbar-thumb {
        background: rgba(255, 30, 30, 0.5);
        border: 2px solid rgba(8, 8, 11, 0.95);
        border-radius: 6px;
      }
      .conv-list::-webkit-scrollbar-thumb:hover {
        background: var(--red);
      }
      .conv-entry {
        position: relative;
        padding: 9px 28px 9px 12px;
        cursor: pointer;
        border-left: 2px solid transparent;
        transition: background 0.15s ease, border-color 0.15s ease;
      }
      .conv-entry:hover {
        background: rgba(255, 30, 30, 0.06);
      }
      .conv-entry.active {
        border-left-color: var(--red);
        background: rgba(255, 30, 30, 0.1);
      }
      .conv-entry .title {
        color: var(--text);
        font-size: 12px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        user-select: text;
      }
      .conv-entry .meta {
        color: var(--text-dim);
        font-size: 9px;
        letter-spacing: 1px;
        margin-top: 2px;
      }
      .conv-entry .x {
        position: absolute;
        top: 6px;
        right: 4px;
        color: var(--red);
        font-size: 18px;
        line-height: 1;
        cursor: pointer;
        padding: 4px 8px;
        opacity: 0.55;
        transition: opacity 0.15s ease, color 0.15s ease, background 0.15s ease;
      }
      .conv-entry:hover .x,
      .conv-entry.active .x {
        opacity: 0.85;
      }
      .conv-entry .x:hover {
        opacity: 1;
        color: var(--red-glow);
        background: rgba(255, 30, 30, 0.15);
      }
      /* Toggle button — small floating tab on left edge */
      .conv-toggle {
        position: fixed;
        top: 78px;
        left: 0;
        z-index: 40;
        background: rgba(8, 8, 11, 0.85);
        border: 1px solid rgba(255, 30, 30, 0.3);
        border-left: none;
        color: var(--red);
        cursor: pointer;
        padding: 8px 6px;
        font-family: "Michroma", monospace;
        font-size: 9px;
        letter-spacing: 2px;
        writing-mode: vertical-rl;
        text-orientation: mixed;
        text-transform: uppercase;
        transition: background 0.15s ease, color 0.15s ease;
      }
      .conv-toggle:hover {
        background: rgba(255, 30, 30, 0.15);
        color: #fff;
      }

      /* Main stage */
      .stage {
        position: relative;
        width: 100vw;
        height: 100vh;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 50px;
        z-index: 5;
      }

      /* Hexagonal mounting plate */
      .panel {
        position: relative;
        width: 480px;
        height: 480px;
        display: flex;
        align-items: center;
        justify-content: center;
        background: radial-gradient(
          circle at 30% 30%,
          #1a1a1f 0%,
          #0a0a0d 60%,
          #050507 100%
        );
        clip-path: polygon(
          50% 0%,
          100% 25%,
          100% 75%,
          50% 100%,
          0% 75%,
          0% 25%
        );
        box-shadow:
          inset 0 0 100px rgba(0, 0, 0, 0.8),
          0 0 40px rgba(0, 0, 0, 0.9);
      }
      .panel::before,
      .panel::after {
        content: "";
        position: absolute;
        width: 8px;
        height: 8px;
        background: radial-gradient(circle, #2a2a2f 30%, #050507 80%);
        border-radius: 50%;
      }
      .panel::before {
        top: 30px;
        left: 50%;
        transform: translateX(-50%);
      }
      .panel::after {
        bottom: 30px;
        left: 50%;
        transform: translateX(-50%);
      }

      /* The eye */
      .eye {
        position: relative;
        width: 320px;
        height: 320px;
        border-radius: 50%;
        cursor: pointer;
        background: radial-gradient(
          circle at 50% 50%,
          #000 35%,
          #1a0000 55%,
          #000 75%
        );
        box-shadow:
          inset 0 0 50px rgba(0, 0, 0, 1),
          inset 0 0 80px rgba(80, 0, 0, 0.8),
          0 0 0 8px #050507,
          0 0 0 10px #1a1a1f,
          0 0 0 12px #050507;
        transition: box-shadow 0.6s ease;
      }

      .iris {
        position: absolute;
        top: 50%;
        left: 50%;
        width: 180px;
        height: 180px;
        transform: translate(-50%, -50%);
        border-radius: 50%;
        background: radial-gradient(
          circle at 50% 50%,
          var(--red-glow) 0%,
          var(--red) 30%,
          var(--red-deep) 60%,
          rgba(80, 0, 0, 0.3) 80%,
          transparent 100%
        );
        opacity: 0.7;
        transition: all 0.6s ease;
        filter: blur(2px);
      }

      .pupil {
        position: absolute;
        top: 50%;
        left: 50%;
        width: 22px;
        height: 22px;
        transform: translate(-50%, -50%);
        border-radius: 50%;
        background: radial-gradient(
          circle at 40% 40%,
          var(--amber-bright) 0%,
          var(--amber) 40%,
          #ff5500 80%,
          #aa3300 100%
        );
        box-shadow:
          0 0 20px var(--amber),
          0 0 40px rgba(255, 180, 0, 0.4);
        transition: all 0.4s ease;
      }

      .specular {
        position: absolute;
        top: 22%;
        left: 28%;
        width: 60px;
        height: 30px;
        border-radius: 50%;
        background: radial-gradient(
          ellipse,
          rgba(255, 255, 255, 0.18) 0%,
          rgba(255, 255, 255, 0.05) 50%,
          transparent 80%
        );
        pointer-events: none;
        filter: blur(4px);
      }

      /* States ----------------------------------------------------------- */

      body.idle .iris {
        opacity: 0.45;
        animation: breathe 5s ease-in-out infinite;
      }
      body.idle .pupil {
        box-shadow: 0 0 10px var(--amber);
      }

      body.listening .iris {
        opacity: 1;
        background: radial-gradient(
          circle at 50% 50%,
          #ff5050 0%,
          var(--red) 30%,
          var(--red-deep) 60%,
          rgba(120, 0, 0, 0.4) 80%,
          transparent 100%
        );
        animation: listen-pulse 1.5s ease-in-out infinite;
      }
      body.listening .pupil {
        background: radial-gradient(
          circle at 40% 40%,
          #ffe070 0%,
          var(--amber) 40%,
          #ff3300 80%
        );
        box-shadow:
          0 0 30px var(--amber),
          0 0 60px rgba(255, 180, 0, 0.6);
      }
      body.listening .eye {
        box-shadow:
          inset 0 0 50px rgba(0, 0, 0, 1),
          inset 0 0 80px rgba(180, 0, 0, 0.7),
          0 0 60px rgba(255, 30, 30, 0.3),
          0 0 0 8px #050507,
          0 0 0 10px #2a1a1a,
          0 0 0 12px #050507;
      }

      body.processing .iris {
        opacity: 1;
        background: radial-gradient(
          circle at 50% 50%,
          #ffb000 0%,
          #ff6600 30%,
          #aa3300 60%,
          transparent 100%
        );
        animation: processing-flicker 0.4s linear infinite;
      }
      body.processing .pupil {
        background: radial-gradient(
          circle at 40% 40%,
          #ffffaa 0%,
          var(--amber-bright) 40%,
          var(--amber) 80%
        );
        animation: processing-pupil 0.6s ease-in-out infinite;
      }
      body.processing .eye {
        box-shadow:
          inset 0 0 50px rgba(0, 0, 0, 1),
          inset 0 0 80px rgba(160, 80, 0, 0.7),
          0 0 50px rgba(255, 150, 0, 0.4),
          0 0 0 8px #050507,
          0 0 0 10px #2a2010,
          0 0 0 12px #050507;
      }

      body.speaking .iris {
        opacity: 1;
        background: radial-gradient(
          circle at 50% 50%,
          #ff4040 0%,
          var(--red) 40%,
          var(--red-deep) 70%,
          transparent 100%
        );
        animation: speak-pulse 0.5s ease-in-out infinite;
      }
      body.speaking .pupil {
        background: radial-gradient(
          circle at 40% 40%,
          var(--amber-bright) 0%,
          var(--amber) 40%,
          #ff3300 80%
        );
        animation: speak-pupil 0.5s ease-in-out infinite;
      }
      body.speaking .eye {
        box-shadow:
          inset 0 0 50px rgba(0, 0, 0, 1),
          inset 0 0 100px rgba(220, 0, 0, 0.8),
          0 0 80px rgba(255, 30, 30, 0.5),
          0 0 0 8px #050507,
          0 0 0 10px #3a1a1a,
          0 0 0 12px #050507;
        animation: eye-speak 0.5s ease-in-out infinite;
      }

      @keyframes breathe {
        0%,
        100% {
          transform: translate(-50%, -50%) scale(0.95);
          opacity: 0.35;
        }
        50% {
          transform: translate(-50%, -50%) scale(1.05);
          opacity: 0.55;
        }
      }
      @keyframes listen-pulse {
        0%,
        100% {
          transform: translate(-50%, -50%) scale(1);
        }
        50% {
          transform: translate(-50%, -50%) scale(1.04);
        }
      }
      @keyframes processing-flicker {
        0%,
        100% {
          opacity: 1;
          transform: translate(-50%, -50%) scale(1);
        }
        25% {
          opacity: 0.7;
          transform: translate(-50%, -50%) scale(0.96);
        }
        50% {
          opacity: 1;
          transform: translate(-50%, -50%) scale(1.02);
        }
        75% {
          opacity: 0.8;
          transform: translate(-50%, -50%) scale(0.98);
        }
      }
      @keyframes processing-pupil {
        0%,
        100% {
          transform: translate(-50%, -50%) scale(1);
        }
        50% {
          transform: translate(-50%, -50%) scale(1.4);
        }
      }
      @keyframes speak-pulse {
        0%,
        100% {
          transform: translate(-50%, -50%) scale(1);
          opacity: 1;
        }
        50% {
          transform: translate(-50%, -50%) scale(1.08);
          opacity: 0.85;
        }
      }
      @keyframes speak-pupil {
        0%,
        100% {
          transform: translate(-50%, -50%) scale(1);
        }
        50% {
          transform: translate(-50%, -50%) scale(1.2);
        }
      }
      @keyframes eye-speak {
        0%,
        100% {
          filter: brightness(1);
        }
        50% {
          filter: brightness(1.15);
        }
      }

      /* Readout */
      .readout {
        text-align: center;
        width: min(820px, 92vw);
        max-height: calc(32vh - 100px);
        overflow-y: auto;
        padding: 0 32px;
        margin-bottom: 80px;
        scrollbar-width: thin;
        scrollbar-color: rgba(255, 30, 30, 0.3) transparent;
      }
      .readout::-webkit-scrollbar {
        width: 4px;
      }
      .readout::-webkit-scrollbar-thumb {
        background: rgba(255, 30, 30, 0.3);
      }
      .state-label {
        font-family: "Michroma", "Share Tech Mono", sans-serif;
        font-size: 13px;
        letter-spacing: 8px;
        color: var(--red);
        text-transform: uppercase;
        margin-bottom: 6px;
        text-shadow: 0 0 12px rgba(255, 30, 30, 0.6);
      }
      .status-subline {
        font-family: "Share Tech Mono", monospace;
        font-size: 11px;
        letter-spacing: 1px;
        color: var(--amber);
        text-align: center;
        min-height: 16px;
        margin-bottom: 14px;
        opacity: 0.8;
        max-width: 720px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        padding: 0 12px;
      }
      .status-subline:empty {
        opacity: 0;
      }
      body.processing .state-label::after,
      body.speaking .state-label::after {
        content: " ●";
        animation: state-pulse 0.8s ease-in-out infinite;
        margin-left: 6px;
      }
      @keyframes state-pulse {
        0%, 100% { opacity: 0.2; }
        50% { opacity: 1; }
      }
      .transcript {
        font-size: 13px;
        color: var(--text);
        letter-spacing: 1px;
        line-height: 1.6;
        opacity: 0.95;
        min-height: 40px;
        white-space: pre-wrap;
        user-select: text;
        text-align: left;
      }
      .chat-log {
        display: flex;
        flex-direction: column;
        gap: 14px;
        padding: 4px 0;
        text-align: left;
      }
      .chat-msg {
        padding: 7px 12px;
        font-size: 12px;
        line-height: 1.55;
        border-left: 2px solid;
        white-space: pre-wrap;
      }
      .chat-msg.user {
        border-left-color: var(--amber);
        color: var(--text-dim);
        background: rgba(255, 179, 0, 0.04);
      }
      .chat-msg.assistant {
        border-left-color: var(--red);
        color: var(--text);
        background: rgba(255, 30, 30, 0.04);
      }
      .chat-role {
        font-size: 9px;
        letter-spacing: 3px;
        color: rgba(255, 30, 30, 0.7);
        text-transform: uppercase;
        margin-bottom: 4px;
        font-family: "Michroma", monospace;
      }
      .chat-msg.user .chat-role {
        color: rgba(255, 179, 0, 0.75);
      }
      .chat-content {
        user-select: text;
      }
      .chat-msg.pending {
        opacity: 0.7;
      }
      .typing-dots {
        display: inline-flex;
        gap: 6px;
        padding: 4px 0;
      }
      .typing-dots span {
        width: 9px;
        height: 9px;
        background: var(--red);
        border-radius: 50%;
        animation: typing-bounce 1.2s ease-in-out infinite;
        box-shadow: 0 0 10px rgba(255, 30, 30, 0.6);
      }
      .typing-dots span:nth-child(2) {
        animation-delay: 0.2s;
      }
      .typing-dots span:nth-child(3) {
        animation-delay: 0.4s;
      }
      @keyframes typing-bounce {
        0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
        30% { transform: translateY(-4px); opacity: 1; }
      }
      .transcript code,
      .transcript pre {
        font-family: "Share Tech Mono", "Courier New", monospace;
        background: rgba(255, 30, 30, 0.08);
        border-left: 2px solid var(--red);
        padding: 1px 4px;
        font-size: 12px;
        color: var(--amber-bright);
      }
      .transcript strong {
        color: var(--amber-bright);
        font-weight: bold;
      }
      .transcript em {
        color: var(--text);
        font-style: italic;
      }
      .transcript ul.md-list {
        list-style: none;
        margin: 4px 0 4px 4px;
        padding: 0;
      }
      .transcript ul.md-list li {
        position: relative;
        padding-left: 14px;
        margin: 3px 0;
      }
      .transcript ul.md-list li::before {
        content: "▸";
        position: absolute;
        left: 0;
        color: var(--red);
      }
      .transcript h3,
      .transcript h4,
      .transcript h5,
      .transcript h6 {
        font-family: "Michroma", monospace;
        color: var(--red);
        font-size: 11px;
        letter-spacing: 3px;
        text-transform: uppercase;
        margin: 8px 0 4px;
      }
      .transcript pre {
        display: block;
        padding: 8px 10px;
        margin: 0;
        overflow-x: auto;
        white-space: pre;
        line-height: 1.4;
      }
      .code-block {
        position: relative;
        margin: 6px 0;
      }
      .code-copy {
        position: absolute;
        top: 4px;
        right: 4px;
        padding: 3px 9px;
        background: rgba(8, 8, 11, 0.85);
        border: 1px solid rgba(255, 30, 30, 0.4);
        color: var(--red);
        font-family: "Michroma", monospace;
        font-size: 9px;
        letter-spacing: 2px;
        cursor: pointer;
        text-transform: uppercase;
        z-index: 1;
        transition: background 0.15s ease, color 0.15s ease, border-color 0.15s ease;
      }
      .code-copy:hover {
        background: rgba(255, 30, 30, 0.2);
        border-color: var(--red);
        color: #fff;
      }
      .code-copy.copied {
        color: var(--amber-bright);
        border-color: var(--amber);
      }
      .readout {
        text-align: left;
      }
      .state-label {
        text-align: center;
      }

      /* Bottom controls group (mic + aux icons) */
      .controls {
        position: absolute;
        bottom: 140px;
        left: 50%;
        transform: translateX(-50%);
        display: flex;
        align-items: center;
        gap: 14px;
        z-index: 20;
        padding: 8px 18px;
        background: rgba(5, 5, 7, 0.96);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 30, 30, 0.3);
        border-radius: 999px;
        box-shadow: 0 4px 24px rgba(0, 0, 0, 0.8);
      }
      .activate {
        width: 72px;
        height: 72px;
        border-radius: 50%;
        padding: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        background: rgba(255, 30, 30, 0.06);
        border: 1px solid rgba(255, 30, 30, 0.3);
        color: var(--red);
        cursor: pointer;
        transition: background 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease, color 0.2s ease;
      }
      .activate .mic-icon {
        width: 30px;
        height: 30px;
        stroke: currentColor;
      }
      .activate:hover:not(:disabled) {
        background: rgba(255, 30, 30, 0.15);
        border-color: var(--red);
        box-shadow: 0 0 30px rgba(255, 30, 30, 0.4);
        color: #fff;
      }
      .activate:disabled {
        opacity: 0.4;
        cursor: not-allowed;
      }
      body.listening .activate {
        background: rgba(255, 30, 30, 0.2);
        border-color: var(--red);
        color: #fff;
        animation: mic-pulse 1.2s ease-in-out infinite;
      }
      @keyframes mic-pulse {
        0%,
        100% {
          transform: scale(1);
          box-shadow: 0 0 28px rgba(255, 30, 30, 0.45);
        }
        50% {
          transform: scale(1.08);
          box-shadow: 0 0 55px rgba(255, 30, 30, 0.75);
        }
      }
      .control-aux {
        width: 44px;
        height: 44px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        background: rgba(255, 30, 30, 0.04);
        border: 1px solid rgba(255, 30, 30, 0.25);
        color: var(--red);
        cursor: pointer;
        padding: 0;
        transition: all 0.2s ease;
      }
      .control-aux:hover {
        background: rgba(255, 30, 30, 0.15);
        border-color: var(--red);
        color: #fff;
        box-shadow: 0 0 20px rgba(255, 30, 30, 0.4);
      }
      .control-aux .aux-icon {
        width: 20px;
        height: 20px;
        stroke: currentColor;
      }

      /* Stop button — only visible while HAL is busy. */
      .stop-btn {
        display: none;
        background: rgba(255, 30, 30, 0.18);
        border-color: rgba(255, 30, 30, 0.55);
      }
      body.processing .stop-btn,
      body.speaking .stop-btn {
        display: flex;
        animation: stop-pulse 1.4s ease-in-out infinite;
      }
      .stop-btn:hover {
        background: rgba(255, 30, 30, 0.32);
        border-color: var(--red);
        color: #fff;
        box-shadow: 0 0 24px rgba(255, 30, 30, 0.55);
      }
      @keyframes stop-pulse {
        0%, 100% { box-shadow: 0 0 10px rgba(255, 30, 30, 0.3); }
        50%      { box-shadow: 0 0 22px rgba(255, 30, 30, 0.6); }
      }

      /* Text directive area (chips + form) */
      .input-area {
        position: absolute;
        bottom: 60px;
        left: 50%;
        transform: translateX(-50%);
        width: min(560px, 92vw);
        z-index: 20;
        display: flex;
        flex-direction: column;
        gap: 6px;
      }
      .attachments {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        min-height: 0;
      }
      .attachments:empty {
        display: none;
      }
      .attachment-chip {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        background: rgba(255, 30, 30, 0.08);
        border: 1px solid rgba(255, 30, 30, 0.3);
        padding: 4px 8px;
        font-family: "Share Tech Mono", monospace;
        font-size: 10px;
        letter-spacing: 1px;
        color: var(--text);
        max-width: 240px;
      }
      .attachment-chip .kind {
        color: var(--amber);
        font-size: 9px;
        letter-spacing: 2px;
        text-transform: uppercase;
      }
      .attachment-chip .name {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        user-select: text;
      }
      .attachment-chip .x {
        cursor: pointer;
        color: var(--red);
        padding: 0 2px;
        font-weight: bold;
      }
      .attachment-chip .x:hover {
        color: var(--red-glow);
      }
      .text-form {
        width: 100%;
        display: flex;
        gap: 8px;
      }
      .text-attach {
        padding: 0 14px;
        background: rgba(255, 30, 30, 0.06);
        border: 1px solid rgba(255, 30, 30, 0.3);
        color: var(--red);
        font-family: "Michroma", monospace;
        font-size: 14px;
        cursor: pointer;
        transition: all 0.2s ease;
        line-height: 1;
      }
      .text-attach:hover {
        background: rgba(255, 30, 30, 0.15);
        border-color: var(--red);
        color: #fff;
      }
      .drop-overlay {
        position: fixed;
        inset: 0;
        background: rgba(255, 30, 30, 0.08);
        border: 4px dashed var(--red);
        z-index: 200;
        display: none;
        align-items: center;
        justify-content: center;
        font-family: "Michroma", monospace;
        color: var(--red-glow);
        font-size: 18px;
        letter-spacing: 8px;
        text-transform: uppercase;
        pointer-events: none;
        backdrop-filter: blur(2px);
        text-shadow: 0 0 20px rgba(255, 30, 30, 0.8);
      }
      .drop-overlay.visible {
        display: flex;
      }

      /* Camera preview overlay */
      .camera-overlay {
        position: fixed;
        inset: 0;
        background: rgba(0, 0, 0, 0.97);
        z-index: 250;
        display: none;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 18px;
        padding: 20px;
      }
      .camera-overlay.open {
        display: flex;
      }
      .camera-overlay video {
        max-width: 92vw;
        max-height: 70vh;
        border: 2px solid var(--red);
        box-shadow: 0 0 40px rgba(255, 30, 30, 0.4);
        background: #000;
      }
      .camera-buttons {
        display: flex;
        gap: 18px;
      }
      .camera-btn {
        padding: 12px 28px;
        font-family: "Michroma", monospace;
        font-size: 11px;
        letter-spacing: 4px;
        text-transform: uppercase;
        background: rgba(255, 30, 30, 0.08);
        border: 1px solid var(--red);
        color: var(--red);
        cursor: pointer;
        transition: background 0.15s ease, color 0.15s ease;
      }
      .camera-btn:hover {
        background: rgba(255, 30, 30, 0.2);
        color: #fff;
      }
      .camera-btn.snap {
        background: rgba(255, 30, 30, 0.2);
        color: #fff;
      }
      .camera-btn.snap:hover {
        background: var(--red);
        box-shadow: 0 0 30px rgba(255, 30, 30, 0.6);
      }

      /* PiP live camera (small corner preview when live vision is active) */
      .camera-pip {
        position: fixed;
        bottom: 240px;
        right: 20px;
        width: 200px;
        height: 150px;
        z-index: 240;
        display: none;
        border: 2px solid var(--red);
        background: #000;
        box-shadow: 0 0 30px rgba(255, 30, 30, 0.5);
        overflow: hidden;
      }
      .camera-pip.active {
        display: block;
      }
      .camera-pip video {
        width: 100%;
        height: 100%;
        object-fit: cover;
      }
      .camera-pip-label {
        position: absolute;
        top: 6px;
        left: 6px;
        background: var(--red);
        color: #fff;
        font-family: "Michroma", monospace;
        font-size: 9px;
        letter-spacing: 2px;
        padding: 3px 8px;
        animation: live-pulse 1.5s ease-in-out infinite;
      }
      .camera-pip-close {
        position: absolute;
        top: 4px;
        right: 4px;
        width: 24px;
        height: 24px;
        border-radius: 50%;
        background: rgba(0, 0, 0, 0.8);
        border: 1px solid var(--red);
        color: var(--red);
        font-size: 16px;
        line-height: 1;
        cursor: pointer;
        padding: 0;
      }
      .camera-pip-close:hover {
        background: var(--red);
        color: #fff;
      }
      @keyframes live-pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.4; }
      }
      .text-input {
        flex: 1;
        padding: 11px 14px;
        background: rgba(255, 30, 30, 0.04);
        border: 1px solid rgba(255, 30, 30, 0.25);
        color: var(--text);
        font-family: "Share Tech Mono", monospace;
        font-size: 12px;
        letter-spacing: 1px;
        outline: none;
        user-select: text;
        caret-color: var(--red);
      }
      .text-input:focus {
        border-color: var(--red);
        background: rgba(255, 30, 30, 0.08);
        box-shadow: 0 0 24px rgba(255, 30, 30, 0.25);
        color: #fff;
      }
      .text-input::placeholder {
        color: var(--text-dim);
        opacity: 0.55;
        letter-spacing: 3px;
      }
      .text-send {
        padding: 0 18px;
        background: rgba(255, 30, 30, 0.06);
        border: 1px solid rgba(255, 30, 30, 0.3);
        color: var(--red);
        font-family: "Michroma", monospace;
        font-size: 10px;
        letter-spacing: 4px;
        cursor: pointer;
        text-transform: uppercase;
        transition: all 0.2s ease;
      }
      .text-send:hover:not(:disabled) {
        background: rgba(255, 30, 30, 0.15);
        border-color: var(--red);
        color: #fff;
      }
      .text-send:disabled {
        opacity: 0.3;
        cursor: not-allowed;
      }

      /* Telemetry panel */
      .telemetry {
        position: fixed;
        top: 70px;
        right: 20px;
        width: 360px;
        max-height: calc(100vh - 220px);
        display: flex;
        flex-direction: column;
        background: rgba(8, 8, 11, 0.9);
        border: 1px solid rgba(255, 30, 30, 0.25);
        z-index: 30;
        backdrop-filter: blur(6px);
        font-family: "Share Tech Mono", monospace;
        box-shadow: 0 0 30px rgba(0, 0, 0, 0.6);
      }
      .telemetry[hidden] {
        display: none;
      }
      .telemetry-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 9px 12px;
        border-bottom: 1px solid rgba(255, 30, 30, 0.2);
        font-size: 9px;
        letter-spacing: 4px;
        color: var(--red);
        text-transform: uppercase;
        background: rgba(255, 30, 30, 0.04);
      }
      .telemetry-clear {
        background: none;
        border: none;
        color: var(--text-dim);
        font-family: inherit;
        font-size: 9px;
        letter-spacing: 2px;
        cursor: pointer;
        text-transform: uppercase;
        padding: 0;
      }
      .telemetry-clear:hover {
        color: var(--red-glow);
      }
      .telemetry-list {
        overflow-y: auto;
        padding: 10px 12px;
        display: flex;
        flex-direction: column;
        gap: 14px;
        scrollbar-width: thin;
        scrollbar-color: rgba(255, 30, 30, 0.3) transparent;
      }
      .telemetry-list::-webkit-scrollbar {
        width: 6px;
      }
      .telemetry-list::-webkit-scrollbar-thumb {
        background: rgba(255, 30, 30, 0.3);
      }
      .telemetry-entry {
        border-left: 2px solid rgba(255, 30, 30, 0.5);
        padding-left: 10px;
      }
      .telemetry-entry.status-error {
        border-left-color: var(--amber);
      }
      .telemetry-entry.status-declined {
        border-left-color: var(--text-dim);
        opacity: 0.7;
      }
      .telemetry-tool {
        color: var(--amber);
        font-size: 9px;
        letter-spacing: 3px;
        text-transform: uppercase;
        margin-bottom: 5px;
      }
      .telemetry-entry.status-error .telemetry-tool {
        color: var(--amber-bright);
      }
      .telemetry-block {
        white-space: pre-wrap;
        word-break: break-word;
        max-height: 220px;
        overflow-y: auto;
        background: rgba(0, 0, 0, 0.35);
        padding: 6px 8px;
        margin: 3px 0;
        font-size: 10.5px;
        line-height: 1.45;
        user-select: text;
      }
      .telemetry-block.input {
        color: var(--text-dim);
        border-left: 1px solid rgba(255, 179, 0, 0.3);
      }
      .telemetry-block.output {
        color: var(--text);
      }
      .telemetry-label {
        font-size: 8px;
        letter-spacing: 2px;
        color: var(--text-dim);
        text-transform: uppercase;
        margin-top: 6px;
        margin-bottom: 2px;
      }

      /* ----- Fullscreen chat mode (hides HAL eye, expands readout) ----- */
      body.fullscreen-chat .panel {
        display: none;
      }
      body.fullscreen-chat .stage {
        justify-content: flex-start;
        padding-top: 70px;
        gap: 14px;
      }
      body.fullscreen-chat .readout {
        max-height: calc(100vh - 280px);
        width: min(960px, 96vw);
      }
      body.fullscreen-chat .state-label {
        font-size: 11px;
        margin-bottom: 8px;
      }
      #fullscreenBtn.active {
        background: rgba(255, 30, 30, 0.25);
        color: #fff;
        box-shadow: 0 0 18px rgba(255, 30, 30, 0.5);
      }

      /* ----- Immersive mode: see-what-HAL-sees ----------------------------- */
      .immersive-stage {
        position: fixed;
        inset: 0;
        z-index: 3;
        background: #000;
        display: none;
        overflow: hidden;
      }
      body.immersive .immersive-stage {
        display: block;
      }
      .immersive-stage > video,
      .immersive-stage > iframe {
        position: absolute;
        inset: 0;
        width: 100%;
        height: 100%;
        border: 0;
        background: #000;
        object-fit: cover;
        display: none;
      }
      .immersive-stage.src-camera > #immVideo,
      .immersive-stage.src-screen > #immVideo,
      .immersive-stage.src-video > #immVideo {
        display: block;
      }
      .immersive-stage.src-screen > #immVideo,
      .immersive-stage.src-video > #immVideo {
        /* Screen / external video: preserve aspect, not cropped. */
        object-fit: contain;
      }
      .immersive-stage.src-map > #immMap {
        display: block;
      }

      /* Dim CRT effects so the backdrop reads clearly */
      body.immersive::before { opacity: 0.35; }
      body.immersive::after  { opacity: 0.55; }
      body.immersive .grid   { display: none; }

      /* Eye docks to bottom-right */
      body.immersive .stage {
        pointer-events: none;
      }
      body.immersive .stage > * {
        pointer-events: auto;
      }
      body.immersive .panel {
        position: fixed;
        right: 18px;
        bottom: 18px;
        width: 150px;
        height: 150px;
        z-index: 60;
        transform: none;
        opacity: 0.92;
        transition: opacity 0.3s ease, transform 0.3s ease, filter 0.3s ease;
        filter: drop-shadow(0 0 18px rgba(255, 30, 30, 0.45));
      }
      body.immersive .panel:hover {
        opacity: 1;
        transform: scale(1.06);
      }
      body.immersive .eye {
        width: 120px;
        height: 120px;
      }
      body.immersive .eye .iris {
        width: 70px;
        height: 70px;
      }
      body.immersive .eye .pupil {
        width: 12px;
        height: 12px;
      }

      /* Fade the rest until interacted with */
      body.immersive .hud,
      body.immersive .footer,
      body.immersive .readout,
      body.immersive .controls,
      body.immersive .input-area,
      body.immersive .conv-toggle,
      body.immersive .conversations,
      body.immersive .telemetry {
        transition: opacity 0.9s ease;
        opacity: 0.08;
      }
      body.immersive .hud:hover,
      body.immersive .hud:focus-within,
      body.immersive .footer:hover,
      body.immersive .readout:hover,
      body.immersive .readout:focus-within,
      body.immersive .controls:hover,
      body.immersive .controls:focus-within,
      body.immersive .input-area:hover,
      body.immersive .input-area:focus-within,
      body.immersive .conv-toggle:hover,
      body.immersive .conversations:hover,
      body.immersive .conversations:focus-within,
      body.immersive .telemetry:hover,
      body.immersive .telemetry:focus-within {
        opacity: 1;
        transition: opacity 0.2s ease;
      }

      /* Source selector bar (top-center of immersive stage) */
      .imm-source-bar {
        position: fixed;
        top: 14px;
        left: 50%;
        transform: translateX(-50%);
        display: none;
        gap: 6px;
        z-index: 65;
        padding: 6px;
        background: rgba(8, 8, 11, 0.6);
        border: 1px solid rgba(255, 30, 30, 0.35);
        backdrop-filter: blur(6px);
        transition: opacity 0.9s ease;
        opacity: 0.12;
      }
      body.immersive .imm-source-bar { display: flex; }
      .imm-source-bar:hover { opacity: 1; transition: opacity 0.2s ease; }
      .imm-source-bar button {
        background: rgba(255, 30, 30, 0.06);
        border: 1px solid rgba(255, 30, 30, 0.3);
        color: var(--text);
        font-family: "Michroma", monospace;
        font-size: 9px;
        letter-spacing: 2px;
        padding: 6px 10px;
        cursor: pointer;
        text-transform: uppercase;
        transition: background 0.15s ease, color 0.15s ease, border-color 0.15s ease;
      }
      .imm-source-bar button:hover {
        background: rgba(255, 30, 30, 0.2);
        color: #fff;
      }
      .imm-source-bar button.active {
        background: rgba(255, 30, 30, 0.3);
        border-color: var(--red);
        color: #fff;
        box-shadow: 0 0 12px rgba(255, 30, 30, 0.4);
      }
      .imm-source-bar .imm-exit {
        border-color: rgba(255, 179, 0, 0.5);
        color: var(--amber);
      }
      .imm-source-bar .imm-exit:hover {
        background: rgba(255, 179, 0, 0.18);
        color: #fff;
      }

      /* HAL's "thoughts" overlay — top-left, ghost text */
      .imm-thoughts {
        position: fixed;
        top: 70px;
        left: 18px;
        width: min(360px, 32vw);
        max-height: 60vh;
        z-index: 55;
        display: none;
        flex-direction: column;
        background: rgba(8, 8, 11, 0.4);
        border-left: 2px solid rgba(255, 179, 0, 0.5);
        padding: 10px 12px;
        font-family: "Share Tech Mono", monospace;
        opacity: 0.35;
        transition: opacity 0.9s ease, background 0.3s ease;
        pointer-events: auto;
      }
      body.immersive .imm-thoughts { display: flex; }
      .imm-thoughts:hover {
        opacity: 1;
        background: rgba(8, 8, 11, 0.85);
        transition: opacity 0.2s ease;
      }
      .imm-thoughts-header {
        font-family: "Michroma", monospace;
        font-size: 9px;
        letter-spacing: 3px;
        color: var(--amber);
        margin-bottom: 8px;
        text-transform: uppercase;
      }
      .imm-thoughts-body {
        overflow-y: auto;
        font-size: 11px;
        line-height: 1.5;
        color: var(--text);
        scrollbar-width: thin;
        scrollbar-color: rgba(255, 179, 0, 0.35) transparent;
      }
      .imm-thoughts-body::-webkit-scrollbar { width: 4px; }
      .imm-thoughts-body::-webkit-scrollbar-thumb {
        background: rgba(255, 179, 0, 0.35);
      }
      .imm-thought {
        margin-bottom: 8px;
        padding-left: 8px;
        border-left: 1px solid rgba(255, 179, 0, 0.25);
        white-space: pre-wrap;
        word-break: break-word;
        user-select: text;
      }
      .imm-thought.tool {
        color: var(--amber);
        font-size: 10px;
        letter-spacing: 1px;
      }
      .imm-thought.hal { color: var(--text); }
      .imm-thought.note {
        color: var(--text-dim);
        font-style: italic;
      }
      .imm-thought .ts {
        color: var(--text-dim);
        font-size: 9px;
        margin-right: 6px;
      }

      /* Map address bar */
      .imm-map-input {
        position: fixed;
        top: 56px;
        left: 50%;
        transform: translateX(-50%);
        z-index: 66;
        display: none;
        gap: 6px;
        background: rgba(8, 8, 11, 0.85);
        border: 1px solid rgba(255, 30, 30, 0.35);
        padding: 6px;
      }
      body.immersive .immersive-stage.src-map ~ .imm-map-input,
      body.immersive .imm-map-input.show { display: flex; }
      .imm-map-input input {
        background: rgba(0, 0, 0, 0.5);
        border: 1px solid rgba(255, 30, 30, 0.3);
        color: var(--text);
        font-family: "Share Tech Mono", monospace;
        font-size: 12px;
        padding: 6px 10px;
        width: 320px;
        outline: none;
      }
      .imm-map-input input:focus { border-color: var(--red); }
      .imm-map-input button {
        background: rgba(255, 30, 30, 0.15);
        border: 1px solid var(--red);
        color: #fff;
        font-family: "Michroma", monospace;
        font-size: 9px;
        letter-spacing: 2px;
        padding: 6px 10px;
        cursor: pointer;
      }

      #immersiveBtn.active {
        background: rgba(255, 179, 0, 0.25);
        color: #fff;
        box-shadow: 0 0 18px rgba(255, 179, 0, 0.55);
      }

      /* ----- Mobile ----- */
      @media (max-width: 768px) {
        html,
        body {
          height: 100dvh;
        }
        .stage {
          height: 100dvh;
          min-height: 100dvh;
          gap: 14px;
          justify-content: flex-start;
          padding: 70px 0 220px;
        }
        .panel {
          width: 240px;
          height: 240px;
        }
        .panel::before {
          top: 14px;
          width: 6px;
          height: 6px;
        }
        .panel::after {
          bottom: 14px;
          width: 6px;
          height: 6px;
        }
        .eye {
          width: 170px;
          height: 170px;
          box-shadow:
            inset 0 0 30px rgba(0, 0, 0, 1),
            inset 0 0 50px rgba(80, 0, 0, 0.8),
            0 0 0 5px #050507,
            0 0 0 7px #1a1a1f,
            0 0 0 9px #050507;
        }
        .iris {
          width: 95px;
          height: 95px;
        }
        .pupil {
          width: 13px;
          height: 13px;
        }
        .specular {
          width: 36px;
          height: 18px;
          top: 24%;
          left: 26%;
        }
        .hud,
        .footer {
          padding: 10px 14px;
          font-size: 8px;
          letter-spacing: 2px;
        }
        .hud-row {
          gap: 12px;
        }
        /* Drop VESSEL and UPTIME on phones to save HUD space. */
        .hud-row > .hud-item:first-of-type {
          display: none;
        }
        .hud-item .label,
        .hud-action .label {
          font-size: 7px;
        }
        .footer {
          font-size: 7px;
          gap: 8px;
          flex-wrap: wrap;
          padding-bottom: calc(6px + env(safe-area-inset-bottom));
        }
        .readout {
          padding: 0 14px;
          max-width: 94vw;
          max-height: 32vh;
          overflow-y: auto;
          scrollbar-width: thin;
          scrollbar-color: rgba(255, 30, 30, 0.3) transparent;
        }
        .readout::-webkit-scrollbar {
          width: 4px;
        }
        .readout::-webkit-scrollbar-thumb {
          background: rgba(255, 30, 30, 0.3);
        }
        .state-label {
          font-size: 10px;
          letter-spacing: 5px;
          margin-bottom: 8px;
        }
        .transcript {
          font-size: 11px;
          letter-spacing: 0.5px;
        }
        .controls {
          bottom: calc(170px + env(safe-area-inset-bottom));
          gap: 12px;
        }
        .activate {
          width: 64px;
          height: 64px;
        }
        .activate .mic-icon {
          width: 26px;
          height: 26px;
        }
        .control-aux {
          width: 40px;
          height: 40px;
        }
        .control-aux .aux-icon {
          width: 18px;
          height: 18px;
        }
        .input-area {
          bottom: calc(70px + env(safe-area-inset-bottom));
          width: 94vw;
        }
        .text-attach {
          padding: 0 12px;
          font-size: 16px;
        }
        .text-input {
          padding: 11px 12px;
          font-size: 16px;
          letter-spacing: 1px;
        }
        .text-send {
          padding: 0 14px;
          font-size: 9px;
          letter-spacing: 3px;
        }
        .conversations {
          top: 56px;
          left: 0;
          width: 100%;
          max-height: 60vh;
          border-left: none;
          border-right: none;
        }
        .conv-toggle {
          top: 60px;
          font-size: 8px;
        }
        .telemetry {
          top: auto;
          right: 0;
          left: 0;
          width: 100%;
          max-height: 40vh;
          border-left: none;
          border-right: none;
          border-bottom: none;
          bottom: calc(48px + env(safe-area-inset-bottom));
        }
        .telemetry-block {
          max-height: 160px;
          font-size: 10px;
        }
        .drop-overlay {
          font-size: 14px;
          letter-spacing: 4px;
        }
      }
    </style>
  </head>
  <body class="idle">
    <div class="grid"></div>

    <!-- Immersive backdrop: see-what-HAL-sees mode -->
    <div class="immersive-stage" id="immStage">
      <video id="immVideo" autoplay playsinline muted crossorigin="anonymous"></video>
      <iframe
        id="immMap"
        title="Map"
        referrerpolicy="no-referrer-when-downgrade"
        allow="geolocation; fullscreen"
        src="about:blank"
      ></iframe>
    </div>
    <div class="imm-source-bar" id="immSourceBar">
      <button type="button" data-imm-src="camera">CAMERA</button>
      <button type="button" data-imm-src="screen">SCREEN</button>
      <button type="button" data-imm-src="map">MAP</button>
      <button type="button" data-imm-src="video">VIDEO</button>
      <button type="button" data-imm-src="off" class="imm-exit">EXIT</button>
    </div>
    <div class="imm-map-input" id="immMapInput">
      <input
        type="text"
        id="immMapAddress"
        placeholder="address, place, or lat,lng"
        autocomplete="off"
      />
      <button type="button" id="immMapGo">GO</button>
    </div>
    <aside class="imm-thoughts" id="immThoughts">
      <div class="imm-thoughts-header">HAL · LIVE COGNITION</div>
      <div class="imm-thoughts-body" id="immThoughtsBody"></div>
    </aside>

    <header class="hud">
      <div class="hud-row">
        <div class="hud-item">
          <div class="label">VESSEL</div>
          <div class="value">DISCOVERY ONE</div>
        </div>
        <div class="hud-item">
          <div class="label">UNIT</div>
          <div class="value">HAL 9000</div>
        </div>
      </div>
      <div class="hud-row">
        <div class="hud-item">
          <div class="label">UPTIME</div>
          <div class="value" id="uptime">00:00:00</div>
        </div>
        <div class="hud-item">
          <div class="label">SYS</div>
          <div class="value" id="sysstate">DORMANT</div>
        </div>
      </div>
    </header>

    <main class="stage">
      <div class="panel">
        <div class="eye" id="eye">
          <div class="iris"></div>
          <div class="pupil"></div>
          <div class="specular"></div>
        </div>
      </div>

      <div class="readout">
        <div class="state-label" id="stateLabel">DORMANT</div>
        <div class="status-subline" id="statusSubline"></div>
        <div class="transcript" id="transcript">
          All systems nominal. Awaiting input.
        </div>
      </div>

      <div class="controls">
        <button
          class="control-aux"
          id="convToggle"
          type="button"
          aria-label="View all conversations"
          title="View all conversations"
        >
          <svg
            class="aux-icon"
            viewBox="0 0 24 24"
            fill="none"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          </svg>
        </button>
        <button
          class="control-aux"
          id="convNewIcon"
          type="button"
          aria-label="New conversation"
          title="New conversation"
        >
          <svg
            class="aux-icon"
            viewBox="0 0 24 24"
            fill="none"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
        </button>
        <button
          class="control-aux"
          id="fastModeBtn"
          type="button"
          aria-label="Toggle fast model"
          title="Toggle fast/smart model (lightning = fast, off = smart)"
        >
          <svg
            class="aux-icon"
            viewBox="0 0 24 24"
            fill="none"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
          </svg>
        </button>
        <button
          class="control-aux"
          id="cameraBtn"
          type="button"
          aria-label="Camera"
          title="Open camera"
        >
          <svg
            class="aux-icon"
            viewBox="0 0 24 24"
            fill="none"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" />
            <circle cx="12" cy="13" r="4" />
          </svg>
        </button>
        <button class="activate" id="btn" type="button" aria-label="Talk">
          <svg
            class="mic-icon"
            viewBox="0 0 24 24"
            fill="none"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <rect x="9" y="3" width="6" height="12" rx="3" />
            <path d="M5 11a7 7 0 0 0 14 0" />
            <line x1="12" y1="18" x2="12" y2="22" />
            <line x1="8" y1="22" x2="16" y2="22" />
          </svg>
        </button>
        <button
          class="control-aux stop-btn"
          id="stopBtn"
          type="button"
          aria-label="Stop HAL"
          title="Stop HAL (interrupt speech / generation)"
        >
          <svg
            class="aux-icon"
            viewBox="0 0 24 24"
            fill="currentColor"
            stroke="none"
          >
            <rect x="6" y="6" width="12" height="12" rx="1" />
          </svg>
        </button>
        <button
          class="control-aux"
          id="fullscreenBtn"
          type="button"
          aria-label="Fullscreen chat"
          title="Toggle fullscreen chat (hide HAL eye)"
        >
          <svg
            class="aux-icon"
            viewBox="0 0 24 24"
            fill="none"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <polyline points="15 3 21 3 21 9" />
            <polyline points="9 21 3 21 3 15" />
            <line x1="21" y1="3" x2="14" y2="10" />
            <line x1="3" y1="21" x2="10" y2="14" />
          </svg>
        </button>
        <button
          class="control-aux"
          id="immersiveBtn"
          type="button"
          aria-label="Immersive mode"
          title="Immersive mode (see what HAL sees)"
        >
          <svg
            class="aux-icon"
            viewBox="0 0 24 24"
            fill="none"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <circle cx="12" cy="12" r="3" />
            <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" />
          </svg>
        </button>
        <button
          class="control-aux"
          id="wipeBtn"
          type="button"
          aria-label="Wipe memory"
          title="Wipe HAL's memory of this conversation"
        >
          <svg
            class="aux-icon"
            viewBox="0 0 24 24"
            fill="none"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <polyline points="3 6 5 6 21 6" />
            <path d="M19 6l-1.5 14a2 2 0 0 1-2 1.8H8.5a2 2 0 0 1-2-1.8L5 6" />
            <path d="M10 11v6" />
            <path d="M14 11v6" />
            <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
          </svg>
        </button>
      </div>

      <div class="input-area">
        <div class="attachments" id="attachments"></div>
        <form class="text-form" id="textForm" autocomplete="off">
          <button
            type="button"
            class="text-attach"
            id="attachBtn"
            aria-label="Attach files"
            title="Attach files (or drag-drop / paste)"
          ><svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
              width="18"
              height="18"
            ><path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" /></svg></button>
          <input
            class="text-input"
            id="textInput"
            type="text"
            placeholder="Or type a directive..."
            maxlength="2000"
            autocomplete="off"
            spellcheck="false"
          />
          <button class="text-send" id="textSend" type="submit">SEND</button>
        </form>
      </div>

      <input
        type="file"
        id="fileInput"
        multiple
        accept="*/*"
        style="
          position: absolute;
          width: 1px;
          height: 1px;
          padding: 0;
          margin: -1px;
          overflow: hidden;
          clip: rect(0, 0, 0, 0);
          white-space: nowrap;
          border: 0;
        "
      />
    </main>

    <div class="drop-overlay" id="dropOverlay">DROP TO ATTACH</div>

    <div class="camera-overlay" id="cameraOverlay">
      <video id="cameraVideo" autoplay playsinline muted></video>
      <div class="camera-buttons">
        <button class="camera-btn" id="cameraCancel" type="button">CANCEL</button>
        <button class="camera-btn" id="cameraFlip" type="button">FLIP</button>
        <button class="camera-btn snap" id="cameraSnap" type="button">SNAP</button>
        <button class="camera-btn snap" id="cameraGoLive" type="button">GO LIVE</button>
      </div>
    </div>

    <div class="camera-pip" id="cameraPip">
      <video id="cameraPipVideo" autoplay playsinline muted></video>
      <div class="camera-pip-label">LIVE</div>
      <button class="camera-pip-close" id="cameraPipClose" type="button" title="Stop live vision">×</button>
    </div>

    <aside class="conversations" id="conversations">
      <div class="conv-header">
        <span>CONVERSATIONS</span>
        <button class="conv-new" id="convNew" type="button">+ NEW</button>
      </div>
      <div class="conv-list" id="convList"></div>
    </aside>

    <aside class="telemetry" id="telemetry" hidden>
      <div class="telemetry-header">
        <span>TELEMETRY</span>
        <button class="telemetry-clear" id="telemetryClear">CLEAR</button>
      </div>
      <div class="telemetry-list" id="telemetryList"></div>
    </aside>

    <footer class="footer">
      <div>HAL/9000 · 9000-SERIES</div>
      <div>QWEN3.6:27B · XTTS-V2 · WHISPER-BASE</div>
    </footer>

    <script>
      const btn = document.getElementById("btn");
      const stateLabel = document.getElementById("stateLabel");
      const transcript = document.getElementById("transcript");
      const sysstate = document.getElementById("sysstate");
      const uptimeEl = document.getElementById("uptime");
      const eyeEl = document.getElementById("eye");
      const textForm = document.getElementById("textForm");
      const textInput = document.getElementById("textInput");
      const textSend = document.getElementById("textSend");
      const wipeBtn = document.getElementById("wipeBtn");
      const telemetryEl = document.getElementById("telemetry");
      const telemetryList = document.getElementById("telemetryList");
      const telemetryClear = document.getElementById("telemetryClear");
      const attachmentsEl = document.getElementById("attachments");
      const attachBtn = document.getElementById("attachBtn");
      const fileInput = document.getElementById("fileInput");
      const dropOverlay = document.getElementById("dropOverlay");
      const convToggle = document.getElementById("convToggle");
      const conversationsEl = document.getElementById("conversations");
      const convList = document.getElementById("convList");
      const convNew = document.getElementById("convNew");
      const body = document.body;
      let currentConversationId = null;

      const MAX_TEXT_ATTACHMENT_BYTES = 200_000;
      const MAX_IMAGE_ATTACHMENT_BYTES = 12_000_000;
      const MAX_ATTACHMENT_COUNT = 50;
      let pendingAttachments = [];

      let ws = null;
      let mediaRecorder = null;
      let micStream = null;
      let audioCtx = null;
      let audioQueue = [];
      let isPlaying = false;
      let streamDone = true;
      let state = "idle";
      // Pre-scheduling state — each incoming chunk is decoded immediately and
      // started at nextChunkStart so playback is gapless and doesn't depend on
      // source.onended (which iOS Safari sometimes drops mid-stream).
      let nextChunkStart = 0;
      let idleTimer = null;
      const bootTime = Date.now();

      setInterval(() => {
        const s = Math.floor((Date.now() - bootTime) / 1000);
        const h = String(Math.floor(s / 3600)).padStart(2, "0");
        const m = String(Math.floor((s % 3600) / 60)).padStart(2, "0");
        const sec = String(s % 60).padStart(2, "0");
        uptimeEl.textContent = `${h}:${m}:${sec}`;
      }, 1000);

      const STATE_LABELS = {
        idle: ["DORMANT", "STANDBY", "IDLE", "AWAITING", "READY"],
        connecting: ["ESTABLISHING LINK", "HANDSHAKE", "CONNECTING", "LINKING"],
        listening: [
          "RECEIVING",
          "LISTENING",
          "EARS OPEN",
          "INTAKE",
          "MIC LIVE",
        ],
        processing: [
          "PROCESSING",
          "THINKING",
          "CRUNCHING",
          "COMPUTING",
          "PARSING",
          "CONSIDERING",
        ],
        speaking: [
          "TRANSMITTING",
          "SPEAKING",
          "BROADCASTING",
          "OUTPUT",
          "REPLYING",
          "VOICE ENGAGED",
        ],
      };
      function pickStateLabel(mode) {
        const opts = STATE_LABELS[mode];
        if (!opts) return mode.toUpperCase();
        return opts[Math.floor(Math.random() * opts.length)];
      }

      async function initAudioContext() {
        if (!audioCtx)
          audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        if (audioCtx.state === "suspended") await audioCtx.resume();
      }

      function escapeHtml(s) {
        return s
          .replace(/&/g, "&amp;")
          .replace(/</g, "&lt;")
          .replace(/>/g, "&gt;");
      }

      function applyInlineMarkdown(text) {
        let s = escapeHtml(text);
        // Bold first (so ** isn't eaten by the italic regex).
        s = s.replace(/\*\*([^\*\n]+)\*\*/g, "<strong>$1</strong>");
        // Italic: single * not adjacent to other *.
        s = s.replace(/(?<![\*\w])\*([^\*\n]+)\*(?![\*\w])/g, "<em>$1</em>");
        // Inline code.
        s = s.replace(/`([^`\n]+)`/g, "<code>$1</code>");
        return s;
      }

      function applyBlockMarkdown(text) {
        const lines = text.split("\n");
        const out = [];
        let inList = false;
        const closeList = () => {
          if (inList) {
            out.push("</ul>");
            inList = false;
          }
        };
        for (const line of lines) {
          const bullet = line.match(/^\s*[\-\*]\s+(.+)/);
          const header = line.match(/^(#{1,4})\s+(.+)/);
          if (bullet) {
            if (!inList) {
              out.push('<ul class="md-list">');
              inList = true;
            }
            out.push(`<li>${applyInlineMarkdown(bullet[1])}</li>`);
          } else if (header) {
            closeList();
            const level = Math.min(6, header[1].length + 2);
            out.push(`<h${level}>${applyInlineMarkdown(header[2])}</h${level}>`);
          } else {
            closeList();
            if (line.trim()) {
              out.push(applyInlineMarkdown(line));
            } else {
              out.push("");
            }
          }
        }
        closeList();
        return out.join("\n");
      }

      function markdownToHtml(text) {
        // 1) Extract fenced code blocks (with copy button) using placeholders
        //    so block-level processing doesn't mangle their contents.
        const placeholders = [];
        const fenceRe = /```(?:[a-zA-Z0-9_-]*)?\n?([\s\S]*?)```/g;
        const withoutCode = text.replace(fenceRe, (_match, code) => {
          const idx = placeholders.length;
          placeholders.push(
            `<div class="code-block"><button type="button" class="code-copy">Copy</button><pre>${escapeHtml(code)}</pre></div>`,
          );
          return `CB${idx}`;
        });
        // 2) Block + inline markdown.
        let html = applyBlockMarkdown(withoutCode);
        // 3) Restore code block placeholders.
        html = html.replace(/CB(\d+)/g, (_m, idx) => placeholders[+idx]);
        return html;
      }

      function renderTranscript(text) {
        // Used for transient status text only — chat log uses renderChatLog.
        transcript.innerHTML = markdownToHtml(text);
      }

      function buildChatMessageEl(role, content) {
        const wrap = document.createElement("div");
        wrap.className = `chat-msg ${role}`;
        const roleEl = document.createElement("div");
        roleEl.className = "chat-role";
        roleEl.textContent = role === "user" ? "JEFFERY" : "HAL";
        wrap.appendChild(roleEl);
        const contentEl = document.createElement("div");
        contentEl.className = "chat-content";
        contentEl.innerHTML = markdownToHtml(content);
        wrap.appendChild(contentEl);
        return wrap;
      }

      function scrollChatLogToBottom() {
        const readout = document.querySelector(".readout");
        if (readout)
          requestAnimationFrame(() => {
            readout.scrollTop = readout.scrollHeight;
          });
      }

      function appendChatMessage(role, content) {
        if (!content) return;
        let log = transcript.querySelector(".chat-log");
        if (!log) {
          transcript.innerHTML = "";
          log = document.createElement("div");
          log.className = "chat-log";
          transcript.appendChild(log);
        }
        log.appendChild(buildChatMessageEl(role, content));
        scrollChatLogToBottom();
      }

      function appendPendingHal() {
        let log = transcript.querySelector(".chat-log");
        if (!log) {
          transcript.innerHTML = "";
          log = document.createElement("div");
          log.className = "chat-log";
          transcript.appendChild(log);
        }
        // Don't double-append if one is already pending.
        if (log.querySelector(".chat-msg.pending")) return;
        const wrap = document.createElement("div");
        wrap.className = "chat-msg assistant pending";
        const role = document.createElement("div");
        role.className = "chat-role";
        role.textContent = "HAL";
        wrap.appendChild(role);
        const content = document.createElement("div");
        content.className = "chat-content";
        content.innerHTML =
          '<div class="typing-dots"><span></span><span></span><span></span></div>';
        wrap.appendChild(content);
        log.appendChild(wrap);
        scrollChatLogToBottom();
      }

      function renderChatLog(messages) {
        transcript.innerHTML = "";
        if (!messages || messages.length === 0) {
          transcript.textContent = "(no messages yet)";
          return;
        }
        const log = document.createElement("div");
        log.className = "chat-log";
        for (const m of messages) {
          if (!m.content) continue;
          log.appendChild(buildChatMessageEl(m.role, m.content));
        }
        transcript.appendChild(log);
        scrollChatLogToBottom();
      }

      transcript.addEventListener("click", async (e) => {
        const btn = e.target.closest(".code-copy");
        if (!btn) return;
        const pre = btn.parentElement.querySelector("pre");
        if (!pre) return;
        try {
          await navigator.clipboard.writeText(pre.textContent);
          btn.classList.add("copied");
          btn.textContent = "Copied";
          setTimeout(() => {
            btn.classList.remove("copied");
            btn.textContent = "Copy";
          }, 1500);
        } catch (err) {
          btn.textContent = "Failed";
          setTimeout(() => (btn.textContent = "Copy"), 1500);
        }
      });

      function renderInline(text) {
        // Inline `code` and escape the rest.
        const out = [];
        const re = /`([^`\n]+)`/g;
        let last = 0;
        let m;
        while ((m = re.exec(text)) !== null) {
          if (m.index > last)
            out.push(escapeHtml(text.slice(last, m.index)));
          out.push(`<code>${escapeHtml(m[1])}</code>`);
          last = m.index + m[0].length;
        }
        if (last < text.length) out.push(escapeHtml(text.slice(last)));
        return out.join("");
      }

      function setMode(mode, labelText, transcriptText) {
        state = mode;
        // Preserve persistent UI-mode classes (immersive, fullscreen-chat)
        // when transitioning between voice states.
        const persistent = [];
        if (body.classList.contains("immersive")) persistent.push("immersive");
        if (body.classList.contains("fullscreen-chat"))
          persistent.push("fullscreen-chat");
        body.className = [mode, ...persistent].join(" ");
        const label = labelText || pickStateLabel(mode);
        stateLabel.textContent = label;
        sysstate.textContent = label;
        // Transient text during processing/speaking goes to the status
        // sub-line so the chat log below stays intact. Idle clears it.
        const sub = document.getElementById("statusSubline");
        if (mode === "idle") {
          if (sub) sub.textContent = "";
          if (transcriptText !== undefined) renderTranscript(transcriptText);
        } else if (transcriptText !== undefined) {
          if (sub) sub.textContent = transcriptText;
        }
      }

      async function onActivate() {
        if (state === "listening") {
          stopRecording();
          return;
        }
        // Mic interrupts whatever HAL is doing. Abort the in-flight turn
        // server-side, drain queued audio, then start fresh recording.
        if (state === "processing" || state === "speaking") {
          try {
            const sock = await ensureSocket();
            sock.send(JSON.stringify({ command: "abort" }));
          } catch {}
          audioQueue = [];
          isPlaying = false;
          nextChunkStart = 0;
          if (idleTimer) {
            clearTimeout(idleTimer);
            idleTimer = null;
          }
          streamDone = true;
        }
        await connectAndRecord();
      }

      function attachWsHandlers(socket) {
        socket.binaryType = "arraybuffer";
        socket.onmessage = (event) => {
          if (event.data instanceof ArrayBuffer) {
            queueAudio(event.data);
          } else {
            try {
              const msg = JSON.parse(event.data);
              if (msg.telemetry) {
                addTelemetry(msg.telemetry);
                return;
              }
              if (msg.conversations) {
                renderConversations(msg.conversations, msg.current_id);
                return;
              }
              if (msg.conversation_history) {
                renderChatLog(msg.conversation_history);
                return;
              }
              if (msg.state === "listening") return;
              if (msg.state === "processing") {
                // A new turn is starting; arm the idle gate.
                streamDone = false;
              }
              if (msg.state === "done") {
                streamDone = true;
                maybeReturnToIdle();
                return;
              }
              setMode(msg.state, undefined, msg.text);
            } catch (e) {
              console.error("JSON parse:", e);
            }
          }
        };
        socket.onerror = () => {
          setMode("idle", "ERROR", "Connection failed.");
          teardown();
        };
        socket.onclose = () => {
          if (state !== "idle" && !isPlaying && audioQueue.length === 0) {
            setMode("idle", "DORMANT", "Link terminated.");
          }
          teardown();
        };
      }

      function ensureSocket() {
        if (ws && ws.readyState === WebSocket.OPEN) return Promise.resolve(ws);
        if (ws && ws.readyState === WebSocket.CONNECTING) {
          return new Promise((resolve, reject) => {
            ws.addEventListener("open", () => resolve(ws), { once: true });
            ws.addEventListener("error", reject, { once: true });
          });
        }
        return new Promise((resolve, reject) => {
          const proto =
            window.location.protocol === "https:" ? "wss:" : "ws:";
          ws = new WebSocket(`${proto}//${window.location.host}/ws`);
          attachWsHandlers(ws);
          ws.addEventListener("open", () => resolve(ws), { once: true });
          ws.addEventListener(
            "error",
            (e) => reject(new Error("WebSocket connect failed")),
            { once: true },
          );
        });
      }

      async function connectAndRecord() {
        try {
          await initAudioContext();
          setMode(
            "processing",
            "ESTABLISHING LINK",
            "Opening neural interface...",
          );
          btn.disabled = true;

          const sock = await ensureSocket();
          sock.send(JSON.stringify({ command: "start" }));
          await startRecording();
        } catch (err) {
          setMode("idle", "ERROR", `Init failed: ${err.message}`);
          teardown();
        }
      }

      async function sendTextDirective(text) {
        const trimmed = (text || "").trim();
        if (!trimmed && pendingAttachments.length === 0 && !liveVisionActive)
          return;
        try {
          await initAudioContext();
          // Live vision: snapshot the current PiP frame and attach it.
          const liveFrame = liveFrameAttachment();
          if (liveFrame) pendingAttachments.push(liveFrame);
          const summary = pendingAttachments.length
            ? ` [+${pendingAttachments.length} attached]`
            : "";
          // Optimistically append to the chat log so user sees their message
          // immediately, instead of waiting for HAL's reply + server refresh.
          appendChatMessage(
            "user",
            `${trimmed || "(attachments only)"}${summary}`,
          );
          appendPendingHal();
          setMode("processing", "PROCESSING");
          textSend.disabled = true;
          btn.disabled = true;
          const sock = await ensureSocket();
          sock.send(
            JSON.stringify({
              command: "text",
              text: trimmed,
              attachments: pendingAttachments.map((a) => ({
                name: a.name,
                kind: a.kind,
                content: a.content,
              })),
              // Live mode prefers the faster vision model; manual snaps don't.
              vision_mode: liveVisionActive ? "fast" : undefined,
              model_mode: fastMode ? "fast" : undefined,
            }),
          );
          textInput.value = "";
          pendingAttachments = [];
          renderAttachments();
        } catch (err) {
          setMode("idle", "ERROR", `Transmit failed: ${err.message}`);
          textSend.disabled = false;
          teardown();
        }
      }

      function startVad(stream) {
        if (!liveVisionActive) {
          console.log("VAD: not started (live mode off)");
          return;
        }
        if (!audioCtx) {
          console.warn("VAD: no audioCtx");
          return;
        }
        try {
          vadSource = audioCtx.createMediaStreamSource(stream);
          vadAnalyser = audioCtx.createAnalyser();
          vadAnalyser.fftSize = 1024;
          vadSource.connect(vadAnalyser);
        } catch (err) {
          console.warn("VAD setup failed:", err);
          return;
        }
        console.log("VAD: started, threshold=", VAD_RMS_THRESHOLD);
        const buf = new Float32Array(vadAnalyser.fftSize);
        let hadSpeech = false;
        let silenceStart = null;
        let logTick = 0;
        vadInterval = setInterval(() => {
          if (!vadAnalyser) return;
          vadAnalyser.getFloatTimeDomainData(buf);
          let sum = 0;
          for (let i = 0; i < buf.length; i++) sum += buf[i] * buf[i];
          const rms = Math.sqrt(sum / buf.length);
          // Log every ~1s so we can see actual mic levels in devtools.
          if (++logTick % 10 === 0) console.log("VAD rms=", rms.toFixed(4));
          if (rms > VAD_RMS_THRESHOLD) {
            hadSpeech = true;
            silenceStart = null;
          } else if (hadSpeech) {
            if (silenceStart === null) silenceStart = Date.now();
            else if (Date.now() - silenceStart > VAD_SILENCE_MS) {
              console.log("VAD: silence detected, auto-transmitting");
              stopVad();
              stopRecording();
            }
          }
        }, 100);
      }

      function stopVad() {
        if (vadInterval) clearInterval(vadInterval);
        vadInterval = null;
        try {
          vadSource?.disconnect();
        } catch {}
        vadSource = null;
        vadAnalyser = null;
      }

      function pickSupportedMimeType() {
        const candidates = [
          "audio/webm;codecs=opus",
          "audio/webm",
          "audio/mp4;codecs=mp4a.40.2",
          "audio/mp4",
          "audio/aac",
          "",
        ];
        for (const c of candidates) {
          if (c === "" || MediaRecorder.isTypeSupported?.(c)) return c;
        }
        return "";
      }

      async function startRecording() {
        if (!navigator.mediaDevices?.getUserMedia) {
          setMode("idle", "ERROR", "Microphone unavailable.");
          teardown();
          return;
        }
        try {
          micStream = await navigator.mediaDevices.getUserMedia({
            audio: true,
          });
          const tracks = micStream.getAudioTracks();
          const trackInfo = tracks
            .map((t) => `${t.label || "unnamed"}(enabled=${t.enabled},muted=${t.muted},readyState=${t.readyState})`)
            .join(", ");
          console.log("Mic tracks:", trackInfo);
          if (tracks.length === 0 || tracks.every((t) => t.muted)) {
            setMode("idle", "ERROR", `No live mic track (${trackInfo || "0 tracks"})`);
            teardown();
            return;
          }
          const mimeType = pickSupportedMimeType();
          console.log("Recording mimeType:", mimeType || "(browser default)");
          mediaRecorder = mimeType
            ? new MediaRecorder(micStream, { mimeType })
            : new MediaRecorder(micStream);
          let chunkCount = 0;
          let totalBytes = 0;
          mediaRecorder.ondataavailable = (e) => {
            chunkCount++;
            totalBytes += e.data.size;
            if (e.data.size > 0 && ws?.readyState === WebSocket.OPEN)
              ws.send(e.data);
          };
          mediaRecorder.onerror = (e) => {
            console.error("MediaRecorder error:", e);
            setMode("idle", "ERROR", `Recorder error: ${e.error?.name || "unknown"}`);
          };
          mediaRecorder.onstop = () => {
            console.log(`Mic stop: ${chunkCount} chunks, ${totalBytes} bytes total`);
            if (ws?.readyState === WebSocket.OPEN) {
              ws.send(
                JSON.stringify({
                  command: "stop",
                  mime: mediaRecorder.mimeType || mimeType || "",
                  model_mode: fastMode ? "fast" : undefined,
                }),
              );
            }
            if (totalBytes === 0) {
              setMode(
                "idle",
                "NO AUDIO",
                `Mic stream produced 0 bytes — check Windows default mic / browser permission. Track: ${trackInfo}`,
              );
            }
            micStream?.getTracks().forEach((t) => t.stop());
            micStream = null;
          };
          mediaRecorder.start(100);
          // Don't pass transcript text — that would wipe the chat log.
          // The pulsing red mic icon is the visual cue that we're listening.
          setMode("listening", "RECEIVING");
          btn.disabled = false;
          startVad(micStream);
        } catch (err) {
          setMode("idle", "ERROR", `Mic denied: ${err.message}`);
          teardown();
        }
      }

      function stopRecording() {
        if (mediaRecorder?.state === "recording") {
          stopVad();
          setMode("processing", "PROCESSING");
          appendChatMessage("user", "(voice)");
          appendPendingHal();
          btn.disabled = true;
          mediaRecorder.stop();
        }
      }

      async function queueAudio(buffer) {
        // iOS Safari can suspend the context between chunks; resume defensively.
        if (audioCtx.state === "suspended") {
          try { await audioCtx.resume(); } catch {}
        }
        let audioBuffer;
        try {
          audioBuffer = await audioCtx.decodeAudioData(buffer.slice(0));
        } catch (err) {
          console.warn("Skip chunk:", err.message);
          return;
        }
        const source = audioCtx.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(audioCtx.destination);
        const now = audioCtx.currentTime;
        // 60ms lead-in keeps the first chunk from clipping; subsequent chunks
        // start exactly when the previous one ends (no gap, no overlap).
        const startAt = isPlaying ? nextChunkStart : now + 0.06;
        source.start(startAt);
        nextChunkStart = startAt + audioBuffer.duration;
        isPlaying = true;

        // Schedule the idle transition for AFTER the last queued chunk ends.
        // Each new chunk pushes this timer back; if the stream ends, the
        // final scheduled timer fires once everything has actually played.
        if (idleTimer) clearTimeout(idleTimer);
        const msUntilEnd = Math.max(
          0,
          (nextChunkStart - audioCtx.currentTime) * 1000 + 80,
        );
        idleTimer = setTimeout(() => {
          isPlaying = false;
          maybeReturnToIdle();
        }, msUntilEnd);
      }

      function maybeReturnToIdle() {
        // Only flip back to idle when the server signalled end-of-stream
        // AND playback has actually finished.
        if (!streamDone || isPlaying) return;
        // Preserve HAL's last reply in the transcript by passing undefined.
        setMode("idle", "DORMANT");
        btn.disabled = false;
        textSend.disabled = false;
        // In live mode, immediately re-arm the mic so Jeffery can speak again
        // without tapping anything. Hands-free loop.
        if (liveVisionActive && state === "idle") {
          connectAndRecord().catch((err) =>
            console.warn("Live re-arm failed:", err),
          );
        }
      }

      function teardown() {
        try {
          if (mediaRecorder?.state === "recording") mediaRecorder.stop();
        } catch {}
        micStream?.getTracks().forEach((t) => t.stop());
        micStream = null;
        try {
          ws?.close();
        } catch {}
        ws = null;
        btn.disabled = false;
        textSend.disabled = false;
      }

      btn.addEventListener("click", onActivate);
      eyeEl.addEventListener("click", onActivate);

      textForm.addEventListener("submit", (e) => {
        e.preventDefault();
        sendTextDirective(textInput.value);
      });

      async function wipeMemory() {
        try {
          const sock = await ensureSocket();
          sock.send(JSON.stringify({ command: "reset" }));
          audioQueue = [];
          isPlaying = false;
          nextChunkStart = 0;
          if (idleTimer) {
            clearTimeout(idleTimer);
            idleTimer = null;
          }
          setMode("idle", "DORMANT", "Memory wiped.");
          btn.disabled = false;
          textSend.disabled = false;
          clearTelemetry();
        } catch (err) {
          setMode("idle", "ERROR", `Wipe failed: ${err.message}`);
        }
      }

      wipeBtn.addEventListener("click", wipeMemory);

      const stopBtn = document.getElementById("stopBtn");
      async function stopHal() {
        try {
          const sock = await ensureSocket();
          sock.send(JSON.stringify({ command: "abort" }));
        } catch {}
        audioQueue = [];
        isPlaying = false;
        nextChunkStart = 0;
        if (idleTimer) {
          clearTimeout(idleTimer);
          idleTimer = null;
        }
        streamDone = true;
        const pending = transcript.querySelector(".chat-msg.pending");
        if (pending) pending.remove();
        setMode("idle", "INTERRUPTED");
        btn.disabled = false;
        textSend.disabled = false;
      }
      stopBtn.addEventListener("click", stopHal);

      function addTelemetry(t) {
        telemetryEl.hidden = false;
        const entry = document.createElement("div");
        entry.className = `telemetry-entry status-${t.status || "ok"}`;

        const tool = document.createElement("div");
        tool.className = "telemetry-tool";
        const statusTag =
          t.status && t.status !== "ok" ? ` · ${t.status.toUpperCase()}` : "";
        tool.textContent = `▶ ${t.tool}${statusTag}`;
        entry.appendChild(tool);

        if (t.input) {
          const inLabel = document.createElement("div");
          inLabel.className = "telemetry-label";
          inLabel.textContent = "INPUT";
          entry.appendChild(inLabel);
          const inBlock = document.createElement("div");
          inBlock.className = "telemetry-block input";
          inBlock.textContent = t.input;
          entry.appendChild(inBlock);
        }

        if (t.output) {
          const outLabel = document.createElement("div");
          outLabel.className = "telemetry-label";
          outLabel.textContent = "OUTPUT";
          entry.appendChild(outLabel);
          const outBlock = document.createElement("div");
          outBlock.className = "telemetry-block output";
          outBlock.textContent = t.output;
          entry.appendChild(outBlock);
        }

        telemetryList.appendChild(entry);
        // Cap to last 25 entries to prevent unbounded growth.
        while (telemetryList.children.length > 25) {
          telemetryList.removeChild(telemetryList.firstChild);
        }
        telemetryList.scrollTop = telemetryList.scrollHeight;
      }

      function clearTelemetry() {
        telemetryList.innerHTML = "";
        telemetryEl.hidden = true;
      }

      telemetryClear.addEventListener("click", clearTelemetry);

      // --- Conversations -----------------------------------------------

      function renderConversations(list, activeId) {
        currentConversationId = activeId || null;
        convList.innerHTML = "";
        for (const c of list) {
          const entry = document.createElement("div");
          entry.className = "conv-entry" + (c.id === activeId ? " active" : "");
          entry.dataset.id = c.id;

          const title = document.createElement("div");
          title.className = "title";
          title.title = c.title || "Untitled";
          title.textContent = c.title || "Untitled";
          entry.appendChild(title);

          const meta = document.createElement("div");
          meta.className = "meta";
          const date = c.updated_at
            ? new Date(c.updated_at * 1000).toLocaleString([], {
                month: "short",
                day: "numeric",
                hour: "2-digit",
                minute: "2-digit",
              })
            : "";
          meta.textContent = `${c.message_count || 0} msg · ${date}`;
          entry.appendChild(meta);

          const x = document.createElement("span");
          x.className = "x";
          x.textContent = "×";
          x.title = "Delete";
          x.addEventListener("click", (e) => {
            e.stopPropagation();
            if (!confirm(`Delete "${c.title}"?`)) return;
            ws?.send(
              JSON.stringify({ command: "delete_conversation", id: c.id }),
            );
          });
          entry.appendChild(x);

          entry.addEventListener("click", () => {
            if (c.id === currentConversationId) return;
            ws?.send(
              JSON.stringify({ command: "switch_conversation", id: c.id }),
            );
            audioQueue = [];
            isPlaying = false;
            nextChunkStart = 0;
            transcript.textContent = `(switched to ${c.title || "Untitled"})`;
          });

          convList.appendChild(entry);
        }
      }

      convToggle.addEventListener("click", () => {
        conversationsEl.classList.toggle("open");
      });

      async function startNewConversation() {
        try {
          const sock = await ensureSocket();
          sock.send(JSON.stringify({ command: "new_conversation" }));
          audioQueue = [];
          isPlaying = false;
          nextChunkStart = 0;
          transcript.textContent = "(new conversation)";
        } catch (err) {
          flashAttachmentError(`New chat failed: ${err.message}`);
        }
      }

      convNew.addEventListener("click", startNewConversation);
      document
        .getElementById("convNewIcon")
        .addEventListener("click", startNewConversation);

      // --- Attachments -------------------------------------------------

      function renderAttachments() {
        attachmentsEl.innerHTML = "";
        pendingAttachments.forEach((a, idx) => {
          const chip = document.createElement("div");
          chip.className = "attachment-chip";

          const kind = document.createElement("span");
          kind.className = "kind";
          kind.textContent = a.kind === "image" ? "IMG" : "TXT";
          chip.appendChild(kind);

          const name = document.createElement("span");
          name.className = "name";
          name.title = a.name;
          name.textContent = a.name;
          chip.appendChild(name);

          const x = document.createElement("span");
          x.className = "x";
          x.textContent = "×";
          x.title = "Remove";
          x.addEventListener("click", () => {
            pendingAttachments.splice(idx, 1);
            renderAttachments();
          });
          chip.appendChild(x);

          attachmentsEl.appendChild(chip);
        });
      }

      function readFileAsText(file) {
        return new Promise((resolve, reject) => {
          const r = new FileReader();
          r.onload = () => resolve(r.result);
          r.onerror = reject;
          r.readAsText(file);
        });
      }

      function readFileAsDataURL(file) {
        return new Promise((resolve, reject) => {
          const r = new FileReader();
          r.onload = () => resolve(r.result);
          r.onerror = reject;
          r.readAsDataURL(file);
        });
      }

      function flashAttachmentError(msg) {
        // Surface attach status/errors in the status sub-line, NOT the
        // transcript. Writing to transcript.textContent wipes the
        // .chat-log element, which then makes the next user message look
        // like a brand-new conversation when appendChatMessage recreates it.
        const sub = document.getElementById("statusSubline");
        if (sub) {
          const text = `! ${msg}`;
          sub.textContent = text;
          setTimeout(() => {
            if (sub.textContent === text) sub.textContent = "";
          }, 4000);
        }
        console.info("[attach]", msg);
      }

      async function addFileAsAttachment(file, displayName) {
        if (pendingAttachments.length >= MAX_ATTACHMENT_COUNT) {
          flashAttachmentError("Attachment limit reached");
          return;
        }
        const name = displayName || file.name || "unnamed";
        const isImage = (file.type || "").startsWith("image/");
        try {
          if (isImage) {
            if (file.size > MAX_IMAGE_ATTACHMENT_BYTES) {
              flashAttachmentError(`Skipping ${name}: image > 4MB`);
              return;
            }
            const dataUrl = await readFileAsDataURL(file);
            const base64 = dataUrl.split(",", 2)[1] || "";
            if (!base64) {
              flashAttachmentError(`Could not read ${name}`);
              return;
            }
            pendingAttachments.push({
              name,
              kind: "image",
              content: base64,
            });
          } else {
            if (file.size > MAX_TEXT_ATTACHMENT_BYTES) {
              flashAttachmentError(`Skipping ${name}: text > 200KB`);
              return;
            }
            const text = await readFileAsText(file);
            if (text.includes("\0")) {
              flashAttachmentError(`Skipping ${name}: binary file`);
              return;
            }
            pendingAttachments.push({
              name,
              kind: "text",
              content: text,
            });
          }
          renderAttachments();
        } catch (err) {
          flashAttachmentError(`Failed to read ${name}: ${err.message || err}`);
        }
      }

      // Recursively walk a dropped folder entry into flat files w/ paths.
      async function walkEntry(entry, path = "") {
        if (entry.isFile) {
          const file = await new Promise((res, rej) => entry.file(res, rej));
          return [{ file, path: path + file.name }];
        }
        if (entry.isDirectory) {
          const reader = entry.createReader();
          const all = [];
          // readEntries returns batches; keep reading until empty.
          while (true) {
            const batch = await new Promise((res, rej) =>
              reader.readEntries(res, rej),
            );
            if (!batch.length) break;
            for (const e of batch) {
              all.push(...(await walkEntry(e, path + entry.name + "/")));
            }
          }
          return all;
        }
        return [];
      }

      attachBtn.addEventListener("click", () => {
        flashAttachmentError("Opening picker...");
        try {
          fileInput.click();
        } catch (err) {
          flashAttachmentError(`Picker failed: ${err.message || err}`);
        }
      });
      fileInput.addEventListener("change", async () => {
        const files = Array.from(fileInput.files || []);
        if (files.length === 0) {
          flashAttachmentError("No file picked.");
          return;
        }
        flashAttachmentError(`Picked ${files.length} file(s), reading...`);
        let added = 0;
        for (const file of files) {
          const before = pendingAttachments.length;
          await addFileAsAttachment(file);
          if (pendingAttachments.length > before) added++;
        }
        fileInput.value = "";
        if (added > 0) {
          flashAttachmentError(`Attached ${added} file(s) — tap SEND.`);
        }
      });

      // Drag-and-drop on the whole page
      let dragDepth = 0;
      window.addEventListener("dragenter", (e) => {
        if (!e.dataTransfer || !Array.from(e.dataTransfer.types).includes("Files")) return;
        e.preventDefault();
        dragDepth++;
        dropOverlay.classList.add("visible");
      });
      window.addEventListener("dragover", (e) => {
        if (!e.dataTransfer || !Array.from(e.dataTransfer.types).includes("Files")) return;
        e.preventDefault();
      });
      window.addEventListener("dragleave", (e) => {
        if (!e.dataTransfer || !Array.from(e.dataTransfer.types).includes("Files")) return;
        dragDepth = Math.max(0, dragDepth - 1);
        if (dragDepth === 0) dropOverlay.classList.remove("visible");
      });
      window.addEventListener("drop", async (e) => {
        if (!e.dataTransfer) return;
        e.preventDefault();
        dragDepth = 0;
        dropOverlay.classList.remove("visible");
        const items = e.dataTransfer.items;
        if (items && items.length) {
          for (const item of items) {
            if (item.kind !== "file") continue;
            const entry = item.webkitGetAsEntry?.();
            if (entry) {
              const files = await walkEntry(entry);
              for (const f of files) {
                await addFileAsAttachment(f.file, f.path);
              }
            } else {
              const file = item.getAsFile();
              if (file) await addFileAsAttachment(file);
            }
          }
        } else {
          for (const file of e.dataTransfer.files || []) {
            await addFileAsAttachment(file);
          }
        }
      });

      // --- Camera ------------------------------------------------------
      const cameraBtn = document.getElementById("cameraBtn");
      const cameraOverlay = document.getElementById("cameraOverlay");
      const cameraVideo = document.getElementById("cameraVideo");
      const cameraSnap = document.getElementById("cameraSnap");
      const cameraCancel = document.getElementById("cameraCancel");
      const cameraFlip = document.getElementById("cameraFlip");
      const cameraGoLive = document.getElementById("cameraGoLive");
      const cameraPip = document.getElementById("cameraPip");
      const cameraPipVideo = document.getElementById("cameraPipVideo");
      const cameraPipClose = document.getElementById("cameraPipClose");
      let cameraStream = null;
      let cameraFacing = "environment"; // start with back camera on mobile
      let liveVisionActive = false;
      let fastMode = false; // text LLM: false = qwen3.6:27b (smart), true = llama3.2:3b (fast)
      // VAD (voice activity detection) for live mode: auto-stop recording
      // after a stretch of silence following speech.
      let vadInterval = null;
      let vadAnalyser = null;
      let vadSource = null;
      const VAD_SILENCE_MS = 1400;
      const VAD_RMS_THRESHOLD = 0.01;
      let liveAnalyzeTimer = null;
      const LIVE_ANALYZE_INTERVAL_MS = 10000;
      const LIVE_VISION_PROMPT =
        "Describe what is in the foreground of this image — objects, tools, devices, food, anything the person is holding, working on, or pointing at. Ignore the person's clothing and the room background. 1-3 sentences.";

      async function openCamera() {
        try {
          cameraStream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: cameraFacing },
            audio: false,
          });
          cameraVideo.srcObject = cameraStream;
          cameraOverlay.classList.add("open");
        } catch (err) {
          flashAttachmentError(`Camera failed: ${err.message || err}`);
        }
      }

      function closeCamera() {
        cameraOverlay.classList.remove("open");
        // Keep the stream alive if we're handing off to live-vision mode.
        if (!liveVisionActive && cameraStream) {
          cameraStream.getTracks().forEach((t) => t.stop());
          cameraStream = null;
          cameraVideo.srcObject = null;
        }
      }

      async function flipCamera() {
        cameraFacing = cameraFacing === "environment" ? "user" : "environment";
        if (cameraStream) {
          cameraStream.getTracks().forEach((t) => t.stop());
        }
        try {
          cameraStream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: cameraFacing },
            audio: false,
          });
          cameraVideo.srcObject = cameraStream;
          if (liveVisionActive) cameraPipVideo.srcObject = cameraStream;
        } catch (err) {
          flashAttachmentError(`Flip failed: ${err.message || err}`);
        }
      }

      function captureFrameFromVideo(videoEl) {
        if (!videoEl || !videoEl.videoWidth) return null;
        const maxDim = 1280;
        const scale = Math.min(
          1,
          maxDim / Math.max(videoEl.videoWidth, videoEl.videoHeight),
        );
        const canvas = document.createElement("canvas");
        canvas.width = Math.round(videoEl.videoWidth * scale);
        canvas.height = Math.round(videoEl.videoHeight * scale);
        canvas.getContext("2d").drawImage(videoEl, 0, 0, canvas.width, canvas.height);
        let dataUrl;
        try {
          dataUrl = canvas.toDataURL("image/jpeg", 0.85);
        } catch (err) {
          // Cross-origin video tainted the canvas (common with external
          // video URLs that don't send CORS headers). Skip the frame.
          console.warn("captureFrameFromVideo: tainted canvas", err);
          return null;
        }
        return (dataUrl.split(",")[1] || "").trim();
      }

      async function startLiveVision() {
        if (!cameraStream) return;
        liveVisionActive = true;
        cameraPipVideo.srcObject = cameraStream;
        cameraPip.classList.add("active");
        cameraOverlay.classList.remove("open");
        cameraBtn.classList.add("active");
        // Auto-arm the mic so the user can just speak — same gesture
        // (GO LIVE button) granted the camera, so mic permission should
        // already be primed.
        if (state !== "listening") {
          try {
            await connectAndRecord();
          } catch (err) {
            console.warn("Live mode mic start failed:", err);
          }
        }
      }

      async function analyzeLiveFrame(prompt) {
        const frame = liveFrameAttachment();
        if (!frame) {
          flashAttachmentError("No live frame to analyze yet.");
          return;
        }
        try {
          await initAudioContext();
          appendChatMessage("user", `${prompt} [+1 attached]`);
          appendPendingHal();
          setMode("processing", "PROCESSING");
          textSend.disabled = true;
          btn.disabled = true;
          const sock = await ensureSocket();
          sock.send(
            JSON.stringify({
              command: "text",
              text: prompt,
              attachments: [frame],
              vision_mode: "fast",
            }),
          );
        } catch (err) {
          flashAttachmentError(`Analyze failed: ${err.message || err}`);
          textSend.disabled = false;
        }
      }

      function stopLiveVision() {
        liveVisionActive = false;
        if (liveAnalyzeTimer) {
          clearInterval(liveAnalyzeTimer);
          liveAnalyzeTimer = null;
        }
        stopVad();
        cameraPip.classList.remove("active");
        cameraBtn.classList.remove("active");
        if (cameraStream) {
          cameraStream.getTracks().forEach((t) => t.stop());
          cameraStream = null;
        }
        cameraPipVideo.srcObject = null;
        cameraVideo.srcObject = null;
      }

      function captureLiveFrame() {
        // Keep live frames at full vision-model resolution — small objects
        // disappear when we downscale too far.
        // In immersive mode, prefer whatever HAL is currently watching
        // (camera / screen-share / external video). Map (iframe) frames
        // cannot be captured cross-origin — falls through to PiP camera.
        if (
          typeof immersiveActive !== "undefined" &&
          immersiveActive &&
          immVideo &&
          immVideo.srcObject &&
          immVideo.videoWidth > 0
        ) {
          const frame = captureFrameFromVideo(immVideo);
          if (frame) return frame;
        }
        return captureFrameFromVideo(cameraPipVideo);
      }

      function liveFrameAttachment() {
        const immersiveHasFrame =
          typeof immersiveActive !== "undefined" &&
          immersiveActive &&
          immVideo &&
          immVideo.srcObject &&
          immVideo.videoWidth > 0;
        if (!liveVisionActive && !immersiveHasFrame) return null;
        const base64 = captureLiveFrame();
        if (!base64) return null;
        return {
          name: `live-${Date.now()}.jpg`,
          kind: "image",
          content: base64,
        };
      }

      function snapPhoto() {
        const base64 = captureFrameFromVideo(cameraVideo);
        if (!base64) {
          flashAttachmentError("Snap failed: empty image");
          return;
        }
        pendingAttachments.push({
          name: `camera-${Date.now()}.jpg`,
          kind: "image",
          content: base64,
        });
        renderAttachments();
        closeCamera();
        if (!textInput.value.trim()) {
          textInput.value = "What do you see?";
        }
        textInput.focus();
      }

      const fullscreenBtn = document.getElementById("fullscreenBtn");
      fullscreenBtn.addEventListener("click", () => {
        const enabled = body.classList.toggle("fullscreen-chat");
        fullscreenBtn.classList.toggle("active", enabled);
      });

      // ===================================================================
      // Immersive mode: full-screen "see what HAL sees"
      // ===================================================================
      const immersiveBtn = document.getElementById("immersiveBtn");
      const immStage = document.getElementById("immStage");
      const immVideo = document.getElementById("immVideo");
      const immMap = document.getElementById("immMap");
      const immSourceBar = document.getElementById("immSourceBar");
      const immMapInput = document.getElementById("immMapInput");
      const immMapAddress = document.getElementById("immMapAddress");
      const immMapGo = document.getElementById("immMapGo");
      const immThoughtsBody = document.getElementById("immThoughtsBody");

      let immersiveActive = false;
      let immersiveSource = "off"; // 'camera' | 'screen' | 'map' | 'video' | 'off'
      let immersiveStream = null;

      function pushThought(kind, text) {
        if (!immThoughtsBody) return;
        if (!text) return;
        const div = document.createElement("div");
        div.className = `imm-thought ${kind}`;
        const ts = document.createElement("span");
        ts.className = "ts";
        const d = new Date();
        ts.textContent = `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}:${String(d.getSeconds()).padStart(2, "0")}`;
        div.appendChild(ts);
        div.appendChild(document.createTextNode(String(text).slice(0, 600)));
        immThoughtsBody.appendChild(div);
        while (immThoughtsBody.children.length > 40) {
          immThoughtsBody.removeChild(immThoughtsBody.firstChild);
        }
        immThoughtsBody.scrollTop = immThoughtsBody.scrollHeight;
      }

      // Tap into existing pipelines so the thoughts panel mirrors them.
      const _origAddTelemetry = addTelemetry;
      addTelemetry = function (t) {
        _origAddTelemetry(t);
        if (!immersiveActive) return;
        const label = `${t.tool}${t.status && t.status !== "ok" ? " · " + t.status : ""}`;
        pushThought("tool", `▶ ${label}`);
        if (t.output) {
          const head = String(t.output).split("\n").slice(0, 2).join(" ").trim();
          if (head) pushThought("note", head.slice(0, 200));
        }
      };

      const _origRenderChatLog = renderChatLog;
      renderChatLog = function (messages) {
        _origRenderChatLog(messages);
        if (!immersiveActive || !messages || !messages.length) return;
        const last = messages[messages.length - 1];
        if (last && last.role === "assistant" && last.content) {
          pushThought("hal", last.content);
        }
      };

      function stopImmersiveStream() {
        if (immersiveStream) {
          immersiveStream.getTracks().forEach((t) => t.stop());
          immersiveStream = null;
        }
        immVideo.srcObject = null;
        immVideo.removeAttribute("src");
        immVideo.load && immVideo.load();
      }

      function applySourceClass(src) {
        immStage.classList.remove(
          "src-camera",
          "src-screen",
          "src-map",
          "src-video",
        );
        if (src === "camera") immStage.classList.add("src-camera");
        else if (src === "screen") immStage.classList.add("src-screen");
        else if (src === "map") immStage.classList.add("src-map");
        else if (src === "video") immStage.classList.add("src-video");
        immSourceBar.querySelectorAll("button").forEach((b) => {
          b.classList.toggle("active", b.dataset.immSrc === src);
        });
        immMapInput.classList.toggle("show", src === "map");
      }

      async function setImmersiveSource(src) {
        // Tear down any prior media first.
        stopImmersiveStream();
        immMap.src = "about:blank";

        if (src === "off") {
          immersiveSource = "off";
          applySourceClass("off");
          exitImmersive();
          return;
        }

        try {
          if (src === "camera") {
            immersiveStream = await navigator.mediaDevices.getUserMedia({
              video: { facingMode: "environment", width: { ideal: 1280 } },
              audio: false,
            });
            immVideo.srcObject = immersiveStream;
            await immVideo.play().catch(() => {});
            pushThought("note", "Source: rear camera");
          } else if (src === "screen") {
            if (!navigator.mediaDevices.getDisplayMedia) {
              pushThought("note", "Screen-share unavailable in this browser.");
              return;
            }
            immersiveStream = await navigator.mediaDevices.getDisplayMedia({
              video: { frameRate: { ideal: 15 } },
              audio: false,
            });
            immVideo.srcObject = immersiveStream;
            await immVideo.play().catch(() => {});
            // If user stops sharing from the browser bar, fall back gracefully.
            immersiveStream.getVideoTracks()[0].addEventListener("ended", () => {
              if (immersiveSource === "screen") setImmersiveSource("off");
            });
            pushThought("note", "Source: screen share");
          } else if (src === "map") {
            const q = (immMapAddress.value || "").trim() || "New York, NY";
            immMap.src = `https://www.google.com/maps?q=${encodeURIComponent(q)}&output=embed`;
            pushThought("note", `Source: map · ${q}`);
            pushThought(
              "note",
              "Note: HAL cannot see inside the map iframe directly. Tell him what to look at, or use SCREEN to share the map.",
            );
          } else if (src === "video") {
            const url = window.prompt(
              "Video URL (mp4/webm direct link, or any HTML5-playable URL):",
              "",
            );
            if (!url) {
              applySourceClass(immersiveSource);
              return;
            }
            immVideo.src = url;
            immVideo.muted = false;
            immVideo.play().catch((err) => {
              pushThought("note", `Video play failed: ${err.message}`);
            });
            pushThought("note", `Source: video · ${url}`);
          }
          immersiveSource = src;
          applySourceClass(src);
        } catch (err) {
          pushThought("note", `Source error: ${err.message}`);
          console.warn("Immersive source error:", err);
        }
      }

      function enterImmersive() {
        immersiveActive = true;
        body.classList.add("immersive");
        immersiveBtn.classList.add("active");
        pushThought("note", "Immersive mode engaged.");
        // Default to camera if nothing is selected yet.
        if (immersiveSource === "off") setImmersiveSource("camera");
      }

      function exitImmersive() {
        immersiveActive = false;
        body.classList.remove("immersive");
        immersiveBtn.classList.remove("active");
        stopImmersiveStream();
        immMap.src = "about:blank";
        immStage.classList.remove(
          "src-camera",
          "src-screen",
          "src-map",
          "src-video",
        );
        immersiveSource = "off";
      }

      immersiveBtn.addEventListener("click", () => {
        if (immersiveActive) exitImmersive();
        else enterImmersive();
      });

      immSourceBar.addEventListener("click", (e) => {
        const btn = e.target.closest("button[data-imm-src]");
        if (!btn) return;
        setImmersiveSource(btn.dataset.immSrc);
      });

      function submitMap() {
        if (immersiveSource !== "map") {
          setImmersiveSource("map");
        } else {
          const q = (immMapAddress.value || "").trim();
          if (!q) return;
          immMap.src = `https://www.google.com/maps?q=${encodeURIComponent(q)}&output=embed`;
          pushThought("note", `Map → ${q}`);
        }
      }
      immMapGo.addEventListener("click", submitMap);
      immMapAddress.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          submitMap();
        }
      });

      // ESC exits immersive (unless typing in an input).
      window.addEventListener("keydown", (e) => {
        if (e.key !== "Escape") return;
        const t = e.target;
        if (
          t &&
          (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable)
        )
          return;
        if (immersiveActive) exitImmersive();
      });

      const fastModeBtn = document.getElementById("fastModeBtn");
      fastModeBtn.addEventListener("click", () => {
        fastMode = !fastMode;
        fastModeBtn.classList.toggle("active", fastMode);
        fastModeBtn.title = fastMode
          ? "Fast model on (llama3.2:3b) — click to switch to smart"
          : "Smart model on (qwen3.6:27b) — click to switch to fast";
      });

      cameraBtn.addEventListener("click", () => {
        if (liveVisionActive) stopLiveVision();
        else openCamera();
      });
      cameraCancel.addEventListener("click", closeCamera);
      cameraSnap.addEventListener("click", snapPhoto);
      cameraFlip.addEventListener("click", flipCamera);
      cameraGoLive.addEventListener("click", startLiveVision);
      cameraPipClose.addEventListener("click", stopLiveVision);
      // Tap the PiP video itself to re-trigger an analyze.
      cameraPipVideo.addEventListener("click", () =>
        analyzeLiveFrame(LIVE_VISION_PROMPT),
      );
      cameraPipVideo.style.cursor = "pointer";

      // Paste: capture images and text from clipboard.
      window.addEventListener("paste", async (e) => {
        const items = e.clipboardData?.items;
        if (!items) return;
        let handled = false;
        for (const item of items) {
          if (item.kind === "file") {
            const file = item.getAsFile();
            if (file) {
              await addFileAsAttachment(file, file.name || `pasted-${Date.now()}`);
              handled = true;
            }
          }
        }
        // Only prevent default text paste if we actually grabbed file content
        if (handled && e.target !== textInput) e.preventDefault();
      });

      setMode("idle", "DORMANT", "All systems nominal. Awaiting input.");

      // Pre-open the WebSocket on page load so the conversations panel has
      // data ready before the user clicks anything. AudioContext stays
      // uninitialised — that still requires a user gesture on iOS.
      ensureSocket().catch((err) => {
        console.warn("Pre-open WS failed:", err.message);
      });
    </script>
  </body>
</html>
