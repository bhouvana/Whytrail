# whytrail-langchain

"Why did this chain produce this output" is a provenance question --
which prompt, which retrieved document, which tool call actually shaped
the answer. `whytrail-langchain` answers it by recording every chain/LLM/
tool/retriever step as a `whytrail` provenance node via LangChain's own
callback system.

```python
import whytrail
from whytrail_langchain import WhytrailCallbackHandler

handler = WhytrailCallbackHandler()
with whytrail.trace():
    result = chain.invoke({"question": "What's our refund policy?"}, config={"callbacks": [handler]})

print(handler.why())
```

```
why(chain output):
  == retriever('refund policy') -> 3 document(s) retrieved
  == chain:StuffDocumentsChain(...) -> {'output_text': '...'}
  == llm:gpt-4o-mini(['prompt with retrieved context...']) -> ...
  == chain:RetrievalQA({'query': "What's our refund policy?"}) -> {'output_text': '...'}
```

Use `handler.why()`, not `whytrail.why(result)` directly, unless you've
confirmed your chain returns the exact object its final step produced --
LangChain often transforms a run's output (e.g. extracting one key from a
dict) before handing it back to the caller, and `handler.why()` doesn't
depend on that object identity surviving the trip.
