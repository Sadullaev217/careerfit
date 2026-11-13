# AI providers

The API reads resumes, judges skills, translates terms and writes plans with a language model. All of it
goes through `apps/api/app/llm.py`, and one setting picks the model.

| `LLM_PROVIDER` | Where the model runs | Resume text goes to |
|---|---|---|
| `ollama` (default) | This machine, through Ollama (`LLM_MODEL`, default `qwen3.5:4b`) | Nowhere else |
| `openrouter` | OpenRouter's providers (`OPENROUTER_MODEL`, default `baidu/ernie-5.5-flash-preview:free`) | OpenRouter and the model's provider |

With `openrouter`, Ollama answers whenever OpenRouter fails, for example after the free daily limit
(`OLLAMA_FALLBACK=true`, the default). A job that used Ollama is recorded as Ollama's, so its saved skill
judgements aren't reused for the hosted model.

## Setting up OpenRouter

1. Create an account at https://openrouter.ai.
2. In https://openrouter.ai/settings/privacy, turn off every option that lets providers train on or
   publish prompts, for both paid and free models. Leave input and output logging off.
3. Create a key at https://openrouter.ai/settings/keys and put it in `apps/api/.env` as
   `OPENROUTER_API_KEY`. Never commit it.
4. Set `LLM_PROVIDER=openrouter` in `apps/api/.env` and restart the API.

## Privacy

- Every request sets `provider.data_collection` to `deny`, so OpenRouter routes only to providers that,
  by its records, don't collect or train on prompts. This holds even if the account setting is changed.
- OpenRouter doesn't store prompts unless input/output logging is turned on. It keeps request metadata
  (token counts, timing), not content.
- Providers keep prompts for their own reasons, such as abuse checks. OpenRouter lists each provider's
  retention at https://openrouter.ai/docs/guides/privacy/provider-logging. Baidu, which serves the
  default model, doesn't train on prompts but keeps them for an unstated period, on servers in China.
- The privacy policy and the store privacy answers have to name the provider before a release that uses
  OpenRouter.
- Resume text is never logged by the API, on either provider.

## Limits of the free models

- 20 requests a minute, and 50 a day until $10 of credits has been bought once, then 1,000 a day. The
  limit is per account, so it is shared by everyone using the app. One analysis makes several requests.
- Free models can be withdrawn or start charging, especially previews.
- Some models always reason before answering. ERNIE 5.5 Flash Preview reasons at high effort on every
  request, which adds time that the listed speed doesn't show. Reasoning isn't returned, and the output
  limit is 32,768 tokens so it can't crowd out the answer.

## Changing the model

Any OpenRouter model that supports structured outputs works: set `OPENROUTER_MODEL`. Check its provider's
data policy first, because requests to providers that may collect data are refused.
