# llm-wiki-ingestion
Ingests all types of input for llm-wiki, inspired by Karpathy's idea.

## Sample input test
Sample files are available in `/sample_input` with these formats:
- `sample.pptx`
- `sample.pdf`
- `sample.xlsx`
- `sample.txt`
- `sample.png`
- `sample.md`

Run test:
```bash
python -m unittest discover -s tests -p "test_*.py"
```
