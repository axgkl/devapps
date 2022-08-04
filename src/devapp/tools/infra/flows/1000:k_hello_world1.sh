#!/bin/bash
d='# Hello World Service

https://riptutorial.com/kubernetes/example/28983/hello-world

'
source "%(feature:functions.sh)s"

# part:name eq local
echo '<html>
  <head>
    <title>Hello World!</title>
  </head>
  <body>
    Hello World!
  </body>
</html>' >index.html

K create configmap hello-world --from-file index.html

echo '---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: hello-world
  annotations:
    kubernetes.io/ingress.class: "traefik"
spec:
  rules:
    - http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: hello-world
                port:
                  number: 80

---
apiVersion: v1
kind: Service
metadata:
  name: hello-world
spec:
  ports:
    - port: 80
      protocol: TCP
  selector:
    app: hello-world

---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: hello-world-nginx
spec:
  selector:
    matchLabels:
      app: hello-world
  replicas: 3
  template:
    metadata:
      labels:
        app: hello-world
    spec:
      containers:
        - name: nginx
          image: nginx
          ports:
            - containerPort: 80
          volumeMounts:
            - name: hello-world-volume
              mountPath: /usr/share/nginx/html
      volumes:
        - name: hello-world-volume
          configMap:
            name: hello-world
' >deploy.yaml

K apply -f deploy.yaml

K expose deployment/hello-world-nginx --type="LoadBalancer" --port 80

K get services
