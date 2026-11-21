{{- define "aurai-workspace.labels" -}}
app.kubernetes.io/part-of: aurai
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/instance: {{ .Release.Name }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
aurai.io/environment: {{ .Values.global.environment | quote }}
{{- end -}}
