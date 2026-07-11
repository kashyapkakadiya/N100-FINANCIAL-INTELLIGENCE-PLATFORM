.PHONY: load ratios test report dashboard api clean

load:
	python src/etl/loader.py

ratios:
	python src/analytics/ratios.py

test:
	python -m pytest tests/ --html=output/pytest_report.html --self-contained-html

report:
	python src/reports/portfolio_report.py

dashboard:
	streamlit run src/dashboard/app.py

api:
	uvicorn src.api.main:app --port 8000

clean:
	find . -name "*.pyc" -delete