# Avatar And Voice Plan

Date: 2026-06-27

Focus now: choose the face and the voice before designing video templates.

## Decision Order

1. Pick the voice.
2. Pick the avatar style.
3. Test still avatar + voice.
4. Test animated avatar/lip-sync.
5. Only then design final video templates.

## Voice Criteria

The voice should be:

- clear in Shorts on phone speakers;
- confident but not hypey;
- not too robotic;
- easy to listen to for 30-60 seconds;
- usable for English AI/news content first;
- replaceable later if we find a better model.

First Kokoro voices to test:

- `am_liam`
- `am_michael`
- `am_onyx`
- `am_eric`
- `bm_lewis`
- `bm_daniel`
- `af_sarah`
- `af_nova`
- `af_bella`

Generate samples:

```bash
bash research/avatar-lab/scripts/audition_kokoro_voices.sh
```

Output:

```text
research/avatar-lab/output/voice-auditions/
```

## Avatar Criteria

For phase 1, the avatar should be stylized but premium.

Avoid:

- trying to perfectly impersonate a real person;
- hyper-real close-up face for the whole video;
- extreme expressions;
- messy background;
- small facial details that break during animation.

Good direction:

- tech presenter;
- clean studio lighting;
- modern dark background;
- slightly stylized realism;
- shoulders/head visible;
- neutral confident expression.

## First Avatar Variants

Create/test 3 styles:

1. `Tech Analyst`
   - serious, calm, premium.
   - best for AI agent/news explanations.

2. `Builder Host`
   - warmer, founder/developer energy.
   - best for Codex/Claude/workflow content.

3. `Shorts Narrator`
   - more punchy, high contrast.
   - best for rapid Shorts hooks.

## Success Test

Make a 20-second clip:

```text
avatar still/image + selected voice + one hook
```

Then ask:

- would I publish this as a test Short?
- does the voice annoy me after replay?
- does the avatar feel credible for AI tools?
- does it look too fake in a bad way?

Only after passing this do we test LivePortrait/Wav2Lip.

