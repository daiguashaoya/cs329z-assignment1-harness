from cs329z_hw1.types import  Email,LMCallable,Message
from cs329z_hw1.pipelines.priority import run_priority
from collections import 

def run_daily_digest(emails: list[Email], lm: LMCallable) -> str:
    # 与email一一对应的category,并创建Thread字典