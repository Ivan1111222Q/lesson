import os

def service_ls():
    ls = os.listdir('./Helm/values')
    return ls


   


# def argocd_apps(servic_ls):
#     ls = os.listdir('./Helm/values')
#     for i in ls:
#         for j in servic_ls:
#             if j.split(".")[0] in i.split(".")[0]:
#                print(f"kubectl apply -f ./helm/{i} -n lesson4356")

          
def argocd_apps(servic_ls):

    for service_file in servic_ls:  # service_file: "orders-service.yaml"
        print(f"kubectl apply -f ./Helm/values/{service_file} -n lesson4356")





argocd_apps(service_ls())  



