import logging
from datetime import datetime
#from input import start

logging.basicConfig(filename='logs/logging_{:%Y-%m-%d-%H-%M}.log'.format(datetime.now()),
                    filemode='a',
                    format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                    datefmt='%H:%M:%S',
                    level=logging.INFO)

def main() -> None:
    #from src.cmake.analyzer import CMakeFlagsAnalyzer
    #test = CMakeFlagsAnalyzer("data/simdjson_simdjson_e2ea5fb8de3d3bc783c5110ef9fb618607f94e3c/parent")
    #out = test.analyze()["add_test_flags"]
    #print(out)
    
    from src.crawler import GithubCrawler
    crawl = GithubCrawler(popular=True, limit=200)
    crawl.crawl()
    #start()

if __name__ == '__main__':
    main()