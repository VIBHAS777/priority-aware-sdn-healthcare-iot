.PHONY: run stress fifo compare dashboard clean

run:
	python3 -m src.sdn_health_iot --scenario baseline --policy priority

stress:
	python3 -m src.sdn_health_iot --scenario stress --policy priority

fifo:
	python3 -m src.sdn_health_iot --scenario baseline --policy fifo

compare:
	./run_experiment.sh

dashboard:
	node dashboard/server.js

clean:
	rm -f data/latest_summary*.json data/latest_timeseries*.csv data/latest_flow_table*.json results/*.svg
