# Refresh Engine Auth Provider Options

## Why

OpenCode and Kilo currently expose Google AntiGravity OAuth paths that are no longer acceptable for this project because they can put user Google accounts at risk. Qwen also still exposes a discontinued `qwen-oauth` auth option even though the latest CLI marks `qwen auth` as removed and upstream documentation says the free OAuth tier was discontinued on 2026-04-15.

At the same time, OpenCode/Kilo and Qwen support common API-key providers that should be available through the provider-aware auth UI.

## What Changes

- Remove OpenCode/Kilo Google AntiGravity from provider-aware auth options, auth strategy, bootstrap config, and default provider config.
- Remove Qwen `qwen-oauth` from provider-aware auth options and strategy.
- Add common OpenCode/Kilo API-key provider options.
- Add current Qwen preset API-key provider options and write Qwen settings using provider presets.
- Keep Gemini engine Google OAuth behavior out of scope.

## Impact

- Users can no longer start OpenCode/Kilo Google AntiGravity auth sessions through Skill Runner.
- Users can no longer start Qwen OAuth sessions through Skill Runner.
- Existing OpenCode/Kilo API-key auth behavior remains unchanged and gains more provider choices.
- Qwen API-key auth writes `~/.qwen/settings.json` in the current model provider shape.
