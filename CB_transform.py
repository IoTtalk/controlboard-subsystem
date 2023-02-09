def run(*args):
    # -10000 -> Open, -10001 -> Close

    data = args[0]
    #print("CB_transform.py data : ", data,"\n")
    return data + 10001
