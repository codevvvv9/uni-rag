class AuthError(Exception):
  """自定义认证异常"""
  def __init__(self, *args):
    self.message = args
    super().__init__(*args)