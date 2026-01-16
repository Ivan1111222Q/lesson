# import os

# def service_ls():
#     ls = os.listdir('./Helm/values')
#     return ls


   


# def argocd_apps(servic_ls):
#     ls = os.listdir('./Helm/values')
#     for i in ls:
#         for j in servic_ls:
#             if j.split(".")[0] in i.split(".")[0]:
#                print(f"kubectl apply -f ./helm/{i} -n lesson4356")

          
# def argocd_apps(servic_ls):

#     for service_file in servic_ls:  # service_file: "orders-service.yaml"
#         print(f"kubectl apply -f ./Helm/values/{service_file} -n lesson4356")





# argocd_apps(service_ls())  

import os
import subprocess

def run_command(cmd):
    print(f"▶️  Команда: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.stdout:
        print(f"📋 Вывод: {result.stdout}")
    if result.stderr:
        print(f"⚠️  Ошибки: {result.stderr}")
    print(f"🎯 Код выхода: {result.returncode}")
    print("-" * 40)
    return result



# var_ls = os.system("ls -l")
# type(var_ls)
# print(var_ls)


run_command("python3 test6.py")


